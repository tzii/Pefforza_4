"""Pure Connect 4 game logic.

Kept dependency-free (only NumPy) so it can be unit-tested without spinning up
Gymnasium or Stable-Baselines3.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from pefforza.constants import AI_PLAYER, COLS, EMPTY, HUMAN_PLAYER, ROWS, WIN_LENGTH

Board = NDArray[np.int8]


def empty_board() -> Board:
    """Return a fresh empty board."""
    return np.zeros((ROWS, COLS), dtype=np.int8)


def available_columns(board: Board) -> list[int]:
    """Columns that still have at least one open slot (top row is empty)."""
    return [c for c in range(COLS) if board[0, c] == EMPTY]


def is_column_full(board: Board, col: int) -> bool:
    return bool(board[0, col] != EMPTY)


def is_board_full(board: Board) -> bool:
    return bool(np.all(board != EMPTY))


def next_open_row(board: Board, col: int) -> int:
    """Lowest empty row in ``col`` or -1 if the column is full."""
    for r in range(ROWS - 1, -1, -1):
        if board[r, col] == EMPTY:
            return r
    return -1


def check_winner(board: Board) -> int:
    """Return the player id (1 or 2) that has 4-in-a-row, or 0 if none."""
    # Horizontal
    for r in range(ROWS):
        for c in range(COLS - WIN_LENGTH + 1):
            v = board[r, c]
            if v != EMPTY and np.all(board[r, c : c + WIN_LENGTH] == v):
                return int(v)
    # Vertical
    for r in range(ROWS - WIN_LENGTH + 1):
        for c in range(COLS):
            v = board[r, c]
            if v != EMPTY and np.all(board[r : r + WIN_LENGTH, c] == v):
                return int(v)
    # Diagonal "\"
    for r in range(ROWS - WIN_LENGTH + 1):
        for c in range(COLS - WIN_LENGTH + 1):
            v = board[r, c]
            if v == EMPTY:
                continue
            if all(board[r + i, c + i] == v for i in range(WIN_LENGTH)):
                return int(v)
    # Diagonal "/"
    for r in range(WIN_LENGTH - 1, ROWS):
        for c in range(COLS - WIN_LENGTH + 1):
            v = board[r, c]
            if v == EMPTY:
                continue
            if all(board[r - i, c + i] == v for i in range(WIN_LENGTH)):
                return int(v)
    return 0


def player_to_move(board: Board, first_player: int = AI_PLAYER) -> int:
    """Return the player id (1 or 2) whose turn it is, derived from counts.

    ``first_player`` (default 1) is assumed to have moved first: when the
    counts are equal it is due to move again, when it is one ahead the other
    player is. The board is expected to come from a source that already
    rejected impossible counts (e.g.
    :class:`pefforza.vision.validation.BoardStateValidator`).
    """
    first = int(np.count_nonzero(board == first_player))
    second = int(np.count_nonzero(board == 3 - first_player))
    return first_player if first == second else 3 - first_player


def swap_perspective(board: Board) -> Board:
    """Swap player ids 1 <-> 2 without touching empty cells.

    Used to feed the model a board from "its" perspective regardless of which
    color it is actually playing in the real world.
    """
    out = board.copy()
    out[board == AI_PLAYER] = HUMAN_PLAYER
    out[board == HUMAN_PLAYER] = AI_PLAYER
    return out


__all__ = [
    "Board",
    "available_columns",
    "check_winner",
    "empty_board",
    "is_board_full",
    "is_column_full",
    "next_open_row",
    "player_to_move",
    "swap_perspective",
]
