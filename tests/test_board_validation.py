"""Tests for the physical-board state validator (pure logic, no camera)."""

from __future__ import annotations

import numpy as np
import pytest

from pefforza.constants import COLS, ROWS
from pefforza.rules import empty_board, next_open_row, player_to_move
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


def _ai_consults(validator: BoardStateValidator, grid: np.ndarray, *, ai_is_red: bool) -> bool:
    """Replicates the play_physical SPACE decision with the same building
    blocks the controller uses: accept the state, then check the turn."""
    check = validator.accept(grid)
    if not check.ok or check.reason is not None:
        return False
    ai_token = 1 if ai_is_red else 2
    return player_to_move(grid) == ai_token


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


def test_rejects_unsupported_token_value():
    validator = BoardStateValidator()
    board = _from_moves([3])
    board[ROWS - 1, 2] = 3  # a classifier must never emit this
    result = validator.accept(board)
    assert not result.ok
    assert "token value" in result.reason


def test_rejects_both_colors_winning_at_once():
    validator = BoardStateValidator()
    board = empty_board()
    board[ROWS - 1, 0:4] = 1  # red four on the floor...
    board[ROWS - 2, 0:4] = 2  # ...and a yellow four stacked right on top
    result = validator.accept(board)
    assert not result.ok
    assert "both colors" in result.reason


def test_rejects_winner_with_inconsistent_counts():
    validator = BoardStateValidator()
    board = empty_board()
    board[ROWS - 1, 0:4] = 2  # yellow connect four...
    for r, c in ((ROWS - 1, 4), (ROWS - 2, 4), (ROWS - 3, 4), (ROWS - 1, 5), (ROWS - 2, 5)):
        board[r, c] = 1  # ...but red kept playing five more moves afterwards
    result = validator.accept(board)
    assert not result.ok
    assert "play continued" in result.reason


def test_yellow_first_variant_winner_count_consistency():
    finished = empty_board()
    finished[ROWS - 1, 0:4] = 2  # yellow (first mover) connect four, red three
    finished[ROWS - 1, 4] = 1
    finished[ROWS - 1, 5] = 1
    finished[ROWS - 2, 4] = 1
    assert BoardStateValidator(red_moves_first=False).accept(finished).ok

    continued = empty_board()
    continued[ROWS - 1, 0:4] = 2  # same yellow four...
    continued[ROWS - 1, 4] = 1
    continued[ROWS - 1, 5] = 1
    continued[ROWS - 2, 4] = 1
    continued[ROWS - 2, 5] = 1  # ...but red caught up to level counts afterwards
    result = BoardStateValidator(red_moves_first=False).accept(continued)
    assert not result.ok
    assert "play continued" in result.reason


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


# ------------------------------------------------------- full-round reads
def test_full_round_read_is_accepted():
    """The natural workflow analyzes once per round: the AI's move and the
    human reply both land between two reads."""
    validator = BoardStateValidator()
    assert validator.accept(_from_moves([3, 2])).ok
    result = validator.accept(_from_moves([3, 2, 4, 1]))
    assert result.ok


def test_round_in_same_column_stacks_in_turn_order():
    validator = BoardStateValidator()
    assert validator.accept(empty_board()).ok  # red to move
    result = validator.accept(_from_moves([3, 3]))  # red drops, yellow replies on top
    assert result.ok


def test_round_in_same_column_wrong_order_rejected():
    validator = BoardStateValidator()
    assert validator.accept(_from_moves([3])).ok  # yellow to move
    board = _from_moves([3])
    board[ROWS - 2, 3] = 1  # red stacked first...
    board[ROWS - 3, 3] = 2  # ...but yellow (due to move) somehow ended up above it
    result = validator.accept(board)
    assert not result.ok
    assert "turn order" in result.reason


def test_three_tokens_in_one_read_rejected():
    validator = BoardStateValidator()
    assert validator.accept(_from_moves([3])).ok
    result = validator.accept(_from_moves([3, 2, 4, 1]))
    assert not result.ok
    assert "more than two tokens" in result.reason


def test_round_with_same_color_pair_rejected_directly():
    """Alternation is normally implied by the count parity; the round check
    verifies it explicitly for direct callers."""
    prev = _from_moves([3, 2])  # red to move
    curr = prev.copy()
    curr[ROWS - 1, 4] = 1  # two reds appeared...
    curr[ROWS - 1, 5] = 1  # ...without a yellow reply in between
    result = BoardStateValidator._check_transition(prev, curr)
    assert not result.ok
    assert "do not alternate" in result.reason


def test_round_first_token_midair_rejected_directly():
    prev = _from_moves([3])  # yellow to move
    curr = prev.copy()
    curr[ROWS - 3, 5] = 2  # yellow floating over an empty column
    curr[ROWS - 1, 6] = 1  # red reply elsewhere
    result = BoardStateValidator._check_transition(prev, curr)
    assert not result.ok
    assert "mid-air" in result.reason


def test_round_second_token_midair_rejected_directly():
    prev = _from_moves([3])  # yellow to move
    curr = prev.copy()
    curr[ROWS - 1, 5] = 2  # yellow legal drop
    curr[ROWS - 3, 6] = 1  # red reply floating in an empty column
    result = BoardStateValidator._check_transition(prev, curr)
    assert not result.ok
    assert "mid-air" in result.reason


def test_round_where_first_move_wins_is_rejected_directly():
    prev = _from_moves([0, 6, 0, 6, 0, 6])  # red three-stack col 0, red to move
    curr = _from_moves([0, 6, 0, 6, 0, 6, 0, 2])  # red wins, yellow replied anyway
    result = BoardStateValidator._check_transition(prev, curr)
    assert not result.ok
    assert "mid-round" in result.reason


def test_round_where_first_move_wins_is_rejected_via_accept():
    """End-to-end: the winner/count consistency gate catches it even before
    the transition replay."""
    validator = BoardStateValidator()
    assert validator.accept(_from_moves([0, 6, 0, 6, 0, 6])).ok
    result = validator.accept(_from_moves([0, 6, 0, 6, 0, 6, 0, 2]))
    assert not result.ok
    assert "play continued" in result.reason


# ------------------------------------------------- controller-level cycles
def test_physical_cycle_space_after_each_move_ai_red():
    """SPACE after every single move: the AI must be consulted only on the
    turns it owns."""
    validator = BoardStateValidator()
    states = [empty_board(), _from_moves([3]), _from_moves([3, 2]), _from_moves([3, 2, 4])]
    expected = [True, False, True, False]
    for grid, want in zip(states, expected, strict=True):
        assert _ai_consults(validator, grid, ai_is_red=True) is want


def test_physical_cycle_space_once_per_round_ai_red():
    """SPACE once per full round (AI move + human reply in one read)."""
    validator = BoardStateValidator()
    states = [empty_board(), _from_moves([3, 2]), _from_moves([3, 2, 4, 1])]
    for grid in states:
        assert _ai_consults(validator, grid, ai_is_red=True)


def test_physical_cycle_ai_yellow_waits_for_red_opener():
    validator = BoardStateValidator()
    assert not _ai_consults(validator, empty_board(), ai_is_red=False)
    assert _ai_consults(validator, _from_moves([3]), ai_is_red=False)
    assert not _ai_consults(validator, _from_moves([3, 3]), ai_is_red=False)


def test_rejected_read_does_not_advance_state():
    """A transient misread must not corrupt the accepted history: the next
    correct read still validates against the last good state."""
    validator = BoardStateValidator()
    assert validator.accept(_from_moves([3, 2])).ok
    misread = _from_moves([3, 2, 4])
    misread[0, 6] = 1  # a hand/token seen floating over an empty column
    assert not validator.accept(misread).ok
    assert validator.accept(_from_moves([3, 2, 4])).ok


def test_rejects_moves_after_terminal_state():
    validator = BoardStateValidator()
    red_wins = _from_moves([0, 6, 0, 6, 0, 6, 0])  # four vertical reds in col 0
    assert validator.accept(red_wins).ok
    extra = red_wins.copy()
    extra[next_open_row(extra, 6), 6] = 2  # someone kept playing after the win
    result = validator.accept(extra)
    assert not result.ok
    assert "game is over" in result.reason


def test_terminal_reread_is_accepted():
    validator = BoardStateValidator()
    red_wins = _from_moves([0, 6, 0, 6, 0, 6, 0])
    assert validator.accept(red_wins).ok
    # Pressing SPACE again on the finished board is not an error.
    assert validator.accept(red_wins.copy()).ok


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
