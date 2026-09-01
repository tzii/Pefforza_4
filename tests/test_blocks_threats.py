"""Regression tests for the GUI-reported bug: 'AI didn't block my 4th piece'.

These tests exercise *every* difficulty tier (except the random `easy` one)
playing as P2 against a P1 with three in a row. The block must always be
chosen. They mirror the reported scenario as faithfully as possible:
the AI is on move, the human just placed their 3rd token, and only one
column completes the 4-in-a-row.
"""

from __future__ import annotations

import pytest

from pefforza.agent.difficulty import build_opponent
from pefforza.agent.minimax import (
    find_immediate_win,
    impossible_agent,
    minimax_agent,
    tactical_safety_net,
)
from pefforza.constants import COLS, ROWS
from pefforza.rules import available_columns, empty_board


def _bottom_three_horizontal_starting_at(start_col: int):
    """Human (P1) has three in a row on the bottom; AI (P2) must block."""
    board = empty_board()
    for c in range(start_col, start_col + 3):
        board[ROWS - 1, c] = 1
    return board


def _vertical_three_at(col: int):
    """Human (P1) has a vertical 3-stack; AI (P2) must drop on top."""
    board = empty_board()
    for r in (ROWS - 1, ROWS - 2, ROWS - 3):
        board[r, col] = 1
    return board


def _diagonal_three_supported():
    """Human (P1) has 3 on an ascending diagonal with the 4th square reachable."""
    board = empty_board()
    # Build supports so the diagonal is the only fillable line.
    # Bottom row positions and stacks:
    # / diagonal at (5,0) (4,1) (3,2) needs blocker support at (5,1) and (5,2),(4,2)
    board[ROWS - 1, 0] = 1
    board[ROWS - 1, 1] = 2
    board[ROWS - 2, 1] = 1
    board[ROWS - 1, 2] = 2
    board[ROWS - 2, 2] = 2
    board[ROWS - 3, 2] = 1
    # The winning 4th would be at (ROWS-4, 3); supports at (5,3),(4,3),(3,3).
    board[ROWS - 1, 3] = 2
    board[ROWS - 2, 3] = 2
    board[ROWS - 3, 3] = 2
    return board, 3  # AI must block at column 3


# ---- direct safety-net checks (no search) -------------------------------
def test_find_immediate_win_horizontal():
    board = _bottom_three_horizontal_starting_at(0)
    valid = available_columns(board)
    assert find_immediate_win(board, 1, valid) == 3
    assert find_immediate_win(board, 2, valid) is None


def test_find_immediate_win_vertical():
    board = _vertical_three_at(3)
    valid = available_columns(board)
    assert find_immediate_win(board, 1, valid) == 3


def test_find_immediate_win_returns_none_when_no_threat():
    board = empty_board()
    board[ROWS - 1, 3] = 1  # one piece, no 3-in-a-row
    valid = available_columns(board)
    assert find_immediate_win(board, 1, valid) is None
    assert find_immediate_win(board, 2, valid) is None


def test_tactical_safety_net_blocks_even_with_dumb_inner_agent():
    """A wrapped 'always pick column 0' agent must still block a 3-in-a-row."""

    def dumb(board, my_id, valid):  # noqa: ARG001
        return valid[0]

    safe = tactical_safety_net(dumb)
    # Threat is on bottom row cols 0-2, block is col 3.
    board = _bottom_three_horizontal_starting_at(0)
    chosen = safe(board, my_id=2, valid=available_columns(board))
    assert chosen == 3, "safety net failed to block immediate threat"


def test_tactical_safety_net_takes_win_over_block():
    """If the AI can win this turn, it must win even when the opponent also threatens."""

    def dumb(board, my_id, valid):  # noqa: ARG001
        return valid[0]

    safe = tactical_safety_net(dumb)
    board = empty_board()
    # P2 (AI) has 3 horizontally on row 4, P1 has 3 horizontally on row 5.
    for c in range(3):
        board[ROWS - 2, c] = 2
    for c in range(3):
        board[ROWS - 1, c + 1] = 1
    # AI's winning column is 3 (completes row 4). Blocking would be col 4.
    # Need to fill (5,3) so a token in col 3 lands on (4,3).
    board[ROWS - 1, 3] = 2
    chosen = safe(board, my_id=2, valid=available_columns(board))
    assert chosen == 3, "safety net should prefer winning over blocking"


# ---- end-to-end: every difficulty tier blocks a 3-in-a-row --------------
@pytest.mark.parametrize("difficulty", ["medium", "hard", "impossible"])
@pytest.mark.parametrize("start_col", [0, 1, 2, 3])
def test_difficulty_blocks_horizontal_threat(difficulty: str, start_col: int):
    """Tier must block a horizontal 3-in-a-row no matter where it starts."""
    if start_col + 3 > COLS:
        pytest.skip("3-in-a-row doesn't fit")
    board = _bottom_three_horizontal_starting_at(start_col)
    expected_block = start_col + 3 if start_col + 3 < COLS else start_col - 1
    agent = build_opponent(difficulty, seed=0)
    chosen = agent(board, my_id=2, valid=available_columns(board))
    # The block must complete-or-prevent the 4-in-a-row; valid blockers are
    # immediately before or after the run.
    valid_blockers = set()
    if start_col - 1 >= 0:
        valid_blockers.add(start_col - 1)
    if start_col + 3 < COLS:
        valid_blockers.add(start_col + 3)
    assert chosen in valid_blockers, (
        f"difficulty={difficulty} starting at col {start_col} "
        f"chose {chosen}, expected one of {valid_blockers} (preferred {expected_block})"
    )


@pytest.mark.parametrize("difficulty", ["medium", "hard", "impossible"])
@pytest.mark.parametrize("col", [0, 3, 6])
def test_difficulty_blocks_vertical_threat(difficulty: str, col: int):
    """Tier must drop into a column where the human has 3 stacked."""
    board = _vertical_three_at(col)
    agent = build_opponent(difficulty, seed=0)
    chosen = agent(board, my_id=2, valid=available_columns(board))
    assert chosen == col, f"difficulty={difficulty} failed to block vertical at col {col}"


@pytest.mark.parametrize("difficulty", ["medium", "hard", "impossible"])
def test_minimax_takes_the_win(difficulty: str):
    """If the AI has 3-in-a-row available, it must complete it."""
    board = empty_board()
    # AI (P2) has three in a row on row 5, cols 1-3.
    for c in (1, 2, 3):
        board[ROWS - 1, c] = 2
    # P1 has placed something irrelevant.
    board[ROWS - 1, 6] = 1
    agent = build_opponent(difficulty, seed=0)
    chosen = agent(board, my_id=2, valid=available_columns(board))
    assert chosen in {0, 4}, f"{difficulty} missed the immediate win, chose {chosen}"


# ---- minimax depth-stress: the bug you reported -------------------------
def test_impossible_blocks_even_when_search_is_misled():
    """The exact reported scenario: P1 has 3-in-a-row, AI is on move, only
    one column blocks. The safety net must win this even if minimax somehow
    doesn't see it."""
    board = _bottom_three_horizontal_starting_at(2)  # threat at cols 2,3,4 -> block at 5 (or 1)
    impossible = impossible_agent(time_budget=0.5, seed=0)
    chosen = impossible(board, my_id=2, valid=available_columns(board))
    assert chosen in {1, 5}


def test_minimax_depth_5_blocks_horizontal():
    board = _bottom_three_horizontal_starting_at(0)
    agent = minimax_agent(depth=5, seed=0)
    chosen = agent(board, my_id=2, valid=available_columns(board))
    assert chosen == 3
