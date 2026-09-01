"""Tests for the physical-board state validator (pure logic, no camera)."""

from __future__ import annotations

import numpy as np
import pytest

from pefforza.constants import COLS, ROWS
from pefforza.rules import empty_board, next_open_row
from pefforza.vision.validation import BoardStateValidator


def _from_moves(columns: list[int]) -> np.ndarray:
    """Apply alternating drops, red first (vision view: 1=red, 2=yellow)."""
    board = empty_board()
    player = 1
    for col in columns:
        row = next_open_row(board, col)
        board[row, col] = player
        player = 3 - player
    return board


def test_accepts_empty_board_as_first_read():
    validator = BoardStateValidator()
    assert validator.accept(empty_board()).ok


def test_accepts_mid_game_position_as_first_read():
    """The first read has no history: only structure and counts matter."""
    validator = BoardStateValidator()
    assert validator.accept(_from_moves([3, 3, 2, 4])).ok


def test_valid_progression_is_accepted():
    validator = BoardStateValidator()
    for moves in ([3], [3, 2], [3, 2, 3], [3, 2, 3, 3]):
        result = validator.accept(_from_moves(moves))
        assert result.ok, result.reason


def test_unchanged_reread_is_accepted():
    validator = BoardStateValidator()
    board = _from_moves([3, 2])
    assert validator.accept(board).ok
    assert validator.accept(board.copy()).ok


def test_rejects_floating_token():
    validator = BoardStateValidator()
    board = _from_moves([3, 2])
    board[0, 5] = 1  # token hovering above an empty column
    result = validator.accept(board)
    assert not result.ok
    assert "gravity" in result.reason


def test_rejects_yellow_moving_first():
    validator = BoardStateValidator()
    board = empty_board()
    board[ROWS - 1, 3] = 2  # a lone yellow: counts incompatible with red-first
    result = validator.accept(board)
    assert not result.ok
    assert "token counts" in result.reason


def test_yellow_first_variant_accepts_yellow_opener():
    validator = BoardStateValidator(red_moves_first=False)
    board = empty_board()
    board[ROWS - 1, 3] = 2
    assert validator.accept(board).ok


def test_rejects_double_add():
    validator = BoardStateValidator()
    assert validator.accept(_from_moves([3])).ok
    result = validator.accept(_from_moves([3, 2, 4]))
    assert not result.ok
    assert "more than one token" in result.reason


def test_rejects_disappearing_token():
    validator = BoardStateValidator()
    assert validator.accept(_from_moves([3, 2])).ok
    result = validator.accept(_from_moves([3]))
    assert not result.ok
    assert "disappeared" in result.reason


def test_rejects_recolored_token():
    validator = BoardStateValidator()
    prev = _from_moves([3, 2])  # red at (5,3), yellow at (5,2)
    assert validator.accept(prev).ok
    curr = prev.copy()
    curr[ROWS - 1, 2] = 1  # yellow misread as red
    # Add a legal yellow elsewhere so the color swap alone doesn't break the
    # token-count parity first: the recolor must be what gets rejected.
    curr[next_open_row(curr, 4), 4] = 2
    result = validator.accept(curr)
    assert not result.ok
    assert "changed color" in result.reason


def test_rejects_token_added_midair_over_the_stack():
    """Defense-in-depth branch of the transition check (structure normally
    catches this first); exercise it directly."""
    prev = _from_moves([3])  # one red at the bottom of column 3
    curr = prev.copy()
    curr[0, 3] = 2  # yellow floating two rows above the single red
    result = BoardStateValidator._check_transition(prev, curr)
    assert not result.ok
    assert "mid-air" in result.reason


def test_rejects_moves_after_terminal_state():
    validator = BoardStateValidator()
    red_wins = _from_moves([0, 6, 0, 6, 0, 6, 0])  # four vertical reds in col 0
    assert validator.accept(red_wins).ok
    extra = red_wins.copy()
    extra[next_open_row(extra, 6), 6] = 2  # someone kept playing after the win
    result = validator.accept(extra)
    assert not result.ok
    assert "game is over" in result.reason


def test_cleared_board_after_game_over_starts_a_new_game():
    validator = BoardStateValidator()
    red_wins = _from_moves([0, 6, 0, 6, 0, 6, 0])
    assert validator.accept(red_wins).ok
    result = validator.accept(empty_board())
    assert result.ok
    assert "new game" in result.reason
    # And play resumes normally from the cleared board.
    assert validator.accept(_from_moves([3])).ok


def test_reset_forgets_history():
    validator = BoardStateValidator()
    assert validator.accept(_from_moves([3, 2, 4])).ok
    validator.reset()
    # A wildly different state is fine again: it becomes the new first read.
    assert validator.accept(_from_moves([6, 1, 2, 5])).ok


def test_rejects_wrong_shape():
    validator = BoardStateValidator()
    result = validator.accept(np.zeros((5, COLS), dtype=np.int8))
    assert not result.ok
    assert "6x7" in result.reason


def test_last_accepted_returns_a_copy():
    validator = BoardStateValidator()
    board = _from_moves([3])
    assert validator.accept(board).ok
    snapshot = validator.last_accepted
    assert snapshot is not None
    snapshot[0, 0] = 2  # mutating the snapshot must not corrupt the validator
    still_valid = validator.accept(_from_moves([3, 2]))
    assert still_valid.ok, still_valid.reason


def test_validation_object_truthiness():
    ok = BoardStateValidator().accept(empty_board())
    assert ok and bool(ok)
    rejected = BoardStateValidator().accept(np.zeros((5, COLS), dtype=np.int8))
    assert not rejected and not bool(rejected)


@pytest.mark.parametrize(
    "moves",
    [[3], [3, 2], [3, 2, 3], [3, 2, 3, 4]],
)
def test_partial_games_pass_count_and_structure(moves: list[int]):
    assert BoardStateValidator().accept(_from_moves(moves)).ok
