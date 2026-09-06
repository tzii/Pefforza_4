"""Headless desktop game state and a cancellable, process-backed opponent.

The desktop player is player 1; the AI is player 2. Rendering and event handling
stay in the GUI, so restarting or undoing a game never depends on a search ending.
"""

from __future__ import annotations

import multiprocessing
import operator
import time
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path

import numpy as np

from pefforza.agent.difficulty import DEFAULT_DIFFICULTY, build_opponent
from pefforza.agent.minimax import find_immediate_win
from pefforza.constants import COLS, DEFAULT_MODEL_PATH, ROWS, WIN_LENGTH
from pefforza.envs.connect4_env import Connect4Env
from pefforza.rules import Board, available_columns, check_winner

_WORKER_TIMEOUT_SECONDS = 15.0


def _suggest_move(board: Board, player: int) -> tuple[int | None, str]:
    valid = sorted(available_columns(board), key=lambda col: abs(col - COLS // 2))
    if not valid:
        return None, "The board is full."
    snapshot = board.copy()
    win = find_immediate_win(snapshot, player, valid)
    if win is not None:
        return win, "Complete four in a row."
    block = find_immediate_win(snapshot, 3 - player, valid)
    if block is not None:
        return block, "Block an immediate four-in-a-row threat."
    return valid[0], "Play near the center to create more connections."


class GameSession:
    """One local game; moves are zero-based columns and human always starts.

    Terminal moves retain the last player's ID, as in ``Connect4Env``. Use
    ``game_over`` rather than ``current_player`` to decide whether play can resume.
    """

    def __init__(self, seed: int | None = None) -> None:
        self.seed = seed
        self.restart()

    @property
    def board(self) -> Board:
        return self._env.board

    @property
    def current_player(self) -> int:
        return self._env.current_player

    def restart(self) -> None:
        self._env = Connect4Env()
        self._env.reset(seed=self.seed)
        self.moves: list[int] = []
        self.winner = 0
        self.game_over = False
        self.status = "Your turn. Choose a column."

    def play(self, col: int) -> bool:
        """Apply the current player's move; rejected moves change nothing."""
        try:
            column = operator.index(col)
        except TypeError:
            return False
        if (
            isinstance(col, (bool, np.bool_))
            or self.game_over
            or not 0 <= column < COLS
            or column not in available_columns(self.board)
        ):
            return False
        _, _, terminated, truncated, info = self._env.step(column)
        self.moves.append(column)
        self.winner = int(info.get("winner", 0))
        self.game_over = terminated or truncated
        if self.winner == 1:
            self.status = "You win! Four in a row."
        elif self.winner == 2:
            self.status = "AI wins. Try another round."
        elif self.game_over:
            self.status = "Draw! The board is full."
        elif self.current_player == 2:
            self.status = "AI is thinking..."
        else:
            self.status = "Your turn. Choose a column."
        return True

    def undo(self) -> bool:
        """Replay up to the previous human decision, including after game over."""
        if not self.moves:
            return False
        count = 1 if len(self.moves) % 2 else 2
        history = self.moves[:-count]
        self.restart()
        for col in history:
            self.play(col)
        self.status = "Move undone. Your turn."
        return True

    def hint(self) -> int | None:
        """Explain a quick human move without changing the board or history."""
        if self.game_over or self.current_player != 1:
            return None
        col, reason = _suggest_move(self.board, 1)
        if col is not None:
            self.status = f"Hint: column {col + 1}. {reason}"
        return col

    @property
    def winning_cells(self) -> list[tuple[int, int]]:
        """All winning (row, column) coordinates, including intersecting lines."""
        if not self.winner:
            return []
        cells: set[tuple[int, int]] = set()
        for row in range(ROWS):
            for col in range(COLS):
                for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                    end_row = row + (WIN_LENGTH - 1) * dr
                    end_col = col + (WIN_LENGTH - 1) * dc
                    if not (0 <= end_row < ROWS and 0 <= end_col < COLS):
                        continue
                    line = [(row + i * dr, col + i * dc) for i in range(WIN_LENGTH)]
                    if all(self.board[r, c] == self.winner for r, c in line):
                        cells.update(line)
        return sorted(cells)


def _opponent_loop(
    connection: Connection,
    difficulty: str,
    seed: int | None,
    model_path: Path,
) -> None:
    opponent = None
    try:
        while True:
            job_id, board, player = connection.recv()
            try:
                if opponent is None:
                    opponent = build_opponent(difficulty, seed=seed, model_path=model_path)
                move = opponent(board, player, available_columns(board))
                if isinstance(move, (bool, np.bool_)):
                    raise TypeError("Expected an integer column, not a boolean.")
                move = operator.index(move)
                connection.send((job_id, move, None))
            except Exception as exc:
                connection.send((job_id, None, f"AI move failed ({type(exc).__name__})."))
    except (EOFError, OSError):
        pass
    finally:
        connection.close()


class OpponentWorker:
    """Lazy persistent AI process with at most one outstanding request.

    ``poll`` never waits for a move. Cancel before replacing the board (undo,
    restart, or difficulty change). Cancellation discards all old results and
    permits reuse; closing permanently stops requests.
    """

    def __init__(
        self,
        difficulty: str = DEFAULT_DIFFICULTY,
        seed: int | None = None,
        model_path: Path = DEFAULT_MODEL_PATH,
    ) -> None:
        self.difficulty = difficulty
        self.seed = seed
        self.model_path = model_path
        self.error: str | None = None
        self._context = multiprocessing.get_context("spawn")
        self._process: BaseProcess | None = None
        self._connection: Connection | None = None
        self._pending: tuple[Board, int] | None = None
        self._job_id = 0
        self._started_at = 0.0
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._pending is not None

    def request(self, board: Board, player: int) -> None:
        """Submit a board snapshot, ignoring duplicate requests while busy.

        A pending result remains busy until polled, even if the child has exited.
        Terminal boards and requests after closing are ignored.
        """
        if self._closed or self.busy:
            return
        if board.shape != (ROWS, COLS) or player not in (1, 2):
            raise ValueError("Expected a Connect 4 board and player 1 or 2.")
        snapshot = board.copy()
        if not available_columns(snapshot) or check_winner(snapshot):
            return
        self.error = None
        self._pending = snapshot, player
        self._job_id += 1
        self._started_at = time.monotonic()
        try:
            if self._process is None or not self._process.is_alive():
                self._stop_process()
                self._connection, child_connection = self._context.Pipe()
                try:
                    self._process = self._context.Process(
                        target=_opponent_loop,
                        args=(child_connection, self.difficulty, self.seed, self.model_path),
                        daemon=True,
                    )
                    self._process.start()
                finally:
                    child_connection.close()
            assert self._connection is not None
            self._connection.send((self._job_id, snapshot, player))
        except Exception as exc:
            self.error = f"AI worker could not start ({type(exc).__name__})."
            self._stop_process()

    def poll(self) -> int | None:
        """Return one legal result, or ``None`` while idle or still thinking."""
        if not self.busy:
            return None
        if self.error:
            return self._fallback(self.error)
        assert self._connection is not None
        assert self._process is not None
        try:
            if self._connection.poll():
                job_id, move, error = self._connection.recv()
                if job_id == self._job_id:
                    if error:
                        return self._fallback(error)
                    try:
                        column = operator.index(move)
                    except TypeError:
                        return self._fallback("AI returned an illegal column.")
                    assert self._pending is not None
                    if isinstance(move, (bool, np.bool_)) or column not in available_columns(
                        self._pending[0]
                    ):
                        return self._fallback("AI returned an illegal column.")
                    self._pending = None
                    return column
            if not self._process.is_alive() and not self._connection.poll():
                return self._fallback("AI worker stopped unexpectedly.")
        except (EOFError, OSError, TypeError, ValueError):
            return self._fallback("AI worker disconnected.")
        if time.monotonic() - self._started_at >= _WORKER_TIMEOUT_SECONDS:
            return self._fallback("AI took too long to respond.")
        return None

    def _fallback(self, message: str) -> int | None:
        assert self._pending is not None
        board, player = self._pending
        move, _ = _suggest_move(board, player)
        self.error = f"{message} Using a legal fallback."
        self._pending = None
        self._stop_process()
        return move

    def _stop_process(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._process is not None:
            if self._process.pid is not None:
                if self._process.is_alive():
                    self._process.terminate()
                self._process.join(timeout=0.2)
                if self._process.is_alive():
                    self._process.kill()
                    self._process.join()
            self._process.close()
            self._process = None

    def cancel(self) -> None:
        """Terminate and join any search, discarding every pending result."""
        self._pending = None
        self._job_id += 1
        self.error = None
        self._stop_process()

    def close(self) -> None:
        self._closed = True
        self.cancel()


__all__ = ["GameSession", "OpponentWorker"]
