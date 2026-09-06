"""Desktop game state and real spawn-worker tests, without a display or model."""

from __future__ import annotations

import multiprocessing
import subprocess
import sys
import time

import numpy as np
import pytest

from pefforza.agent.difficulty import build_opponent
from pefforza.cli import gui_game
from pefforza.cli.gui_game import GameSession, OpponentWorker
from pefforza.constants import COLS, ROWS, WIN_LENGTH
from pefforza.rules import available_columns

HUMAN_WIN = [0, 6, 1, 6, 2, 5, 3]
AI_WIN = [0, 6, 1, 6, 2, 6, 4, 6]
DRAW = [
    6,
    1,
    1,
    5,
    1,
    6,
    0,
    1,
    6,
    4,
    0,
    1,
    6,
    4,
    3,
    0,
    6,
    4,
    5,
    5,
    4,
    3,
    1,
    4,
    0,
    5,
    0,
    4,
    0,
    6,
    3,
    3,
    5,
    3,
    3,
    5,
    2,
    2,
    2,
    2,
    2,
    2,
]


def _game(moves=()) -> GameSession:
    game = GameSession(seed=3)
    for col in moves:
        assert game.play(col)
    return game


def _state(game):
    return game.current_player, game.moves.copy(), game.winner, game.game_over, game.status


def test_new_game_and_move_alternation():
    game = _game()
    assert game.board.shape == (ROWS, COLS)
    assert game.board.dtype == np.int8
    assert not game.board.any()
    assert _state(game)[:4] == (1, [], 0, False)
    assert game.winning_cells == []
    assert game.play(np.int64(3))
    assert game.board[-1, 3] == 1
    assert game.current_player == 2
    assert "thinking" in game.status
    assert game.play(3)
    assert game.board[-2, 3] == 2
    assert game.current_player == 1
    assert game.moves == [3, 3]


@pytest.mark.parametrize("column", [-1, COLS, 99, 1.2, "2", None, True, np.bool_(True)])
def test_invalid_moves_leave_everything_unchanged(column):
    game = _game([3, 2])
    board, state = game.board.copy(), _state(game)
    assert not game.play(column)
    np.testing.assert_array_equal(game.board, board)
    assert _state(game) == state


def test_full_column_is_not_a_loss_or_a_turn():
    game = _game([0] * ROWS)
    board, state = game.board.copy(), _state(game)
    assert not game.play(0)
    np.testing.assert_array_equal(game.board, board)
    assert _state(game) == state
    assert game.play(1)


@pytest.mark.parametrize("moves,winner", [(HUMAN_WIN, 1), (AI_WIN, 2), (DRAW, 0)])
def test_terminal_results_lock_board_until_restart(moves, winner):
    game = _game(moves)
    assert game.game_over
    assert game.winner == winner
    assert bool(game.winning_cells) == bool(winner)
    assert ("Draw" in game.status) == (winner == 0)
    board, state = game.board.copy(), _state(game)
    assert not game.play(0)
    assert game.hint() is None
    np.testing.assert_array_equal(game.board, board)
    assert _state(game) == state
    old_env = game._env
    game.restart()
    assert game._env is not old_env
    assert _state(game)[:4] == (1, [], 0, False)
    assert not game.board.any()
    assert game.winning_cells == []
    assert game.play(0)


@pytest.mark.parametrize(
    "moves,remaining",
    [
        ([3], []),
        ([3, 2], []),
        ([3, 2, 4], [3, 2]),
        (HUMAN_WIN, HUMAN_WIN[:-1]),
        (AI_WIN, AI_WIN[:-2]),
        (DRAW, DRAW[:-2]),
    ],
)
def test_undo_returns_to_a_human_decision_point(moves, remaining):
    game = _game(moves)
    old_env = game._env
    assert game.undo()
    assert game._env is not old_env
    assert game.moves == remaining
    assert game.current_player == 1
    assert not game.game_over
    assert game.winner == 0
    assert game.winning_cells == []
    np.testing.assert_array_equal(game.board, _game(remaining).board)
    assert game.play(available_columns(game.board)[0])


def test_undo_empty_game_is_a_noop():
    game = _game()
    state = _state(game)
    assert not game.undo()
    assert _state(game) == state


@pytest.mark.parametrize(
    "moves,column,reason",
    [
        ([], 3, "center"),
        ([3] * ROWS, 2, "center"),
        ([0, 6, 1, 6, 2, 6], 3, "Complete"),
        ([0, 6, 1, 6, 4, 6], 6, "Block"),
    ],
)
def test_hint_explains_win_block_or_center_without_playing(moves, column, reason):
    game = _game(moves)
    board, state = game.board.copy(), _state(game)
    assert game.hint() == column
    assert f"column {column + 1}" in game.status
    assert reason in game.status
    np.testing.assert_array_equal(game.board, board)
    assert _state(game)[:4] == state[:4]


def test_hint_does_not_interrupt_ai_turn():
    game = _game([3])
    state = _state(game)
    assert game.hint() is None
    assert _state(game) == state


@pytest.mark.parametrize("row,col,dr,dc", [(5, 0, 0, 1), (0, 0, 1, 0), (1, 2, 1, 1), (1, 5, 1, -1)])
def test_winning_cells_in_all_directions(row, col, dr, dc):
    game = _game()
    expected = [(row + i * dr, col + i * dc) for i in range(WIN_LENGTH)]
    for r, c in expected:
        game.board[r, c] = 1
    game.winner = 1
    assert game.winning_cells == sorted(expected)


def test_winning_cells_includes_entire_long_line_without_duplicates():
    game = _game()
    game.board[-1, : WIN_LENGTH + 1] = 1
    game.board[-WIN_LENGTH:, 0] = 1
    game.winner = 1
    expected = {(ROWS - 1, c) for c in range(WIN_LENGTH + 1)}
    expected.update((r, 0) for r in range(ROWS - WIN_LENGTH, ROWS))
    assert game.winning_cells == sorted(expected)


def test_controller_and_worker_import_without_pygame_or_model_runtime():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import pefforza.cli.gui_game; "
            "assert not {'pygame', 'torch', 'stable_baselines3'} & sys.modules.keys()",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def worker():
    instance = OpponentWorker("easy", seed=13)
    try:
        yield instance
    finally:
        instance.close()


def _wait_move(worker):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        move = worker.poll()
        if move is not None:
            return move
        time.sleep(0.01)
    pytest.fail("Spawned opponent did not respond within 10 seconds")


def test_worker_is_lazy_spawned_and_keeps_seeded_opponent_between_moves(worker):
    assert worker._context.get_start_method() == "spawn"
    assert worker._process is None
    assert not worker.busy
    assert worker.poll() is None
    game = _game([3])
    expected = build_opponent("easy", seed=13)
    worker.request(game.board, 2)
    process = worker._process
    assert process is not None and process.daemon
    assert worker.busy
    first = _wait_move(worker)
    assert first == expected(game.board, 2, available_columns(game.board))
    assert not worker.busy
    assert worker.error is None
    assert worker.poll() is None
    assert game.play(first)
    assert game.play(3)
    worker.request(game.board, 2)
    assert _wait_move(worker) == expected(game.board, 2, available_columns(game.board))
    assert worker._process is process


def test_worker_snapshots_board_and_ignores_duplicate_requests(worker):
    game = _game(DRAW[:-1])
    assert available_columns(game.board) == [2]
    worker.request(game.board, 2)
    job_id = worker._job_id
    game.board[:] = 0
    worker.request(game.board, 1)
    assert worker._job_id == job_id
    assert _wait_move(worker) == 2
    assert worker.poll() is None


@pytest.mark.parametrize("moves", [HUMAN_WIN, DRAW])
def test_terminal_board_does_not_start_worker(worker, moves):
    worker.request(_game(moves).board, 2)
    assert not worker.busy
    assert worker._process is None


def test_cancel_discards_old_results_joins_child_and_allows_reuse(worker):
    game = _game([3])
    worker.request(game.board, 2)
    pid = worker._process.pid
    worker.cancel()
    assert not worker.busy
    assert worker.poll() is None
    assert worker.error is None
    assert worker._process is None
    assert pid not in [child.pid for child in multiprocessing.active_children()]
    worker.request(game.board, 2)
    expected = build_opponent("easy", seed=13)
    assert _wait_move(worker) == expected(game.board, 2, available_columns(game.board))


def test_close_is_idempotent_and_permanent(worker):
    worker.request(_game([3]).board, 2)
    worker.close()
    worker.close()
    worker.request(_game([3]).board, 2)
    assert not worker.busy
    assert worker._process is None
    assert worker.poll() is None


@pytest.mark.parametrize(
    "moves,expected", [([3], 3), ([0, 6, 1, 6, 2], 3), ([0, 6, 1, 6, 4, 6, 0], 6)]
)
def test_worker_failure_uses_legal_tactical_fallback(worker, moves, expected):
    worker.difficulty = "not-a-difficulty"
    worker.request(_game(moves).board, 2)
    assert _wait_move(worker) == expected
    assert "ValueError" in worker.error
    assert not worker.busy
    assert worker._process is None


def test_worker_crash_returns_fallback_instead_of_hanging(worker):
    worker.request(_game([3]).board, 2)
    worker._process.terminate()
    worker._process.join()
    assert _wait_move(worker) == 3
    assert worker.error
    assert not worker.busy


def test_worker_recovers_after_failed_move_and_clears_error(worker):
    game = _game([3])
    worker.difficulty = "not-a-difficulty"
    worker.request(game.board, 2)
    assert _wait_move(worker) == 3
    assert worker.error
    worker.difficulty = "easy"
    worker.request(game.board, 2)
    assert worker.error is None
    expected = build_opponent("easy", seed=13)
    assert _wait_move(worker) == expected(game.board, 2, available_columns(game.board))
    assert worker.error is None


def test_idle_child_crash_is_replaced_for_next_request(worker):
    game = _game([3])
    worker.request(game.board, 2)
    assert _wait_move(worker) in available_columns(game.board)
    process = worker._process
    process.terminate()
    process.join()
    worker.request(game.board, 2)
    assert worker._process is not process
    assert _wait_move(worker) in available_columns(game.board)
    assert worker.error is None


def test_seeded_worker_and_controller_finish_a_complete_round(worker):
    game = _game()
    human = build_opponent("easy", seed=27)
    while not game.game_over:
        valid = available_columns(game.board)
        if game.current_player == 1:
            move = human(game.board, 1, valid)
        else:
            worker.request(game.board, 2)
            move = _wait_move(worker)
            assert worker.error is None
        assert move in valid
        assert game.play(move)
        assert len(game.moves) == np.count_nonzero(game.board)
    assert len(game.moves) <= ROWS * COLS
    worker.request(game.board, game.current_player)
    assert not worker.busy
    assert worker.poll() is None


def _never_respond(connection, difficulty, seed, model_path):
    connection.recv()
    time.sleep(60)


def _illegal_response(connection, difficulty, seed, model_path):
    job_id, _, _ = connection.recv()
    connection.send((job_id, seed, None))
    connection.close()


def _stale_then_current_response(connection, difficulty, seed, model_path):
    job_id, _, _ = connection.recv()
    connection.send((job_id - 1, 0, None))
    connection.send((job_id, 4, None))
    connection.close()


def test_nonresponsive_worker_has_hard_deadline(worker, monkeypatch):
    monkeypatch.setattr(gui_game, "_opponent_loop", _never_respond)
    monkeypatch.setattr(gui_game, "_WORKER_TIMEOUT_SECONDS", 0)
    worker.request(_game([3]).board, 2)
    pid = worker._process.pid
    assert worker.poll() == 3
    assert "too long" in worker.error
    assert not worker.busy
    assert pid not in [child.pid for child in multiprocessing.active_children()]


@pytest.mark.parametrize("move", [-1, COLS, 1.0, "1", True, None])
def test_illegal_worker_result_is_replaced(worker, monkeypatch, move):
    monkeypatch.setattr(gui_game, "_opponent_loop", _illegal_response)
    worker.seed = move
    worker.request(_game([3]).board, 2)
    assert _wait_move(worker) == 3
    assert "illegal column" in worker.error


def test_worker_result_for_a_full_column_is_replaced(worker, monkeypatch):
    monkeypatch.setattr(gui_game, "_opponent_loop", _illegal_response)
    worker.seed = 3
    game = _game([3] * ROWS + [0])
    worker.request(game.board, 2)
    assert _wait_move(worker) == 2
    assert "illegal column" in worker.error


def test_cancel_discards_a_result_already_buffered_by_child(worker, monkeypatch):
    monkeypatch.setattr(gui_game, "_opponent_loop", _illegal_response)
    worker.seed = 4
    worker.request(_game([3]).board, 2)
    worker._process.join(timeout=10)
    assert not worker._process.is_alive()
    assert worker._connection.poll()
    assert worker.busy
    worker.cancel()
    assert worker.poll() is None
    assert not worker.busy
    assert worker._process is None
    worker.seed = 2
    worker.request(_game([3]).board, 2)
    assert _wait_move(worker) == 2


def test_stale_result_does_not_replace_current_move(worker, monkeypatch):
    monkeypatch.setattr(gui_game, "_opponent_loop", _stale_then_current_response)
    worker.request(_game([3]).board, 2)
    worker._process.join(timeout=10)
    assert not worker._process.is_alive()
    assert _wait_move(worker) == 4
    assert worker.error is None
    assert not worker.busy


def test_worker_start_failure_is_recoverable(worker, monkeypatch):
    def fail_start(**kwargs):
        raise OSError("No process available")

    monkeypatch.setattr(worker._context, "Process", fail_start)
    worker.request(_game([3]).board, 2)
    assert worker.busy
    assert worker.poll() == 3
    assert "could not start" in worker.error
    assert not worker.busy
    assert worker._connection is None
