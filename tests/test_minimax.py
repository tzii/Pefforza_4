"""Behavioural tests for the minimax engine.

These are the most important tests in the project: they prove that the
"hard" / "impossible" difficulty tiers actually play tactically, not just
"better than random on average".
"""

from __future__ import annotations

import time

import numpy as np

from pefforza.agent.minimax import (
    MinimaxAgent,
    evaluate_position,
    impossible_agent,
    minimax_agent,
)
from pefforza.constants import COLS, ROWS
from pefforza.rules import empty_board


def test_takes_immediate_win():
    """Three-in-a-row on the bottom: minimax must complete it."""
    board = empty_board()
    board[ROWS - 1, 0] = 1
    board[ROWS - 1, 1] = 1
    board[ROWS - 1, 2] = 1
    agent = MinimaxAgent(depth=3, seed=0)
    col = agent.select(board, my_id=1, valid=list(range(COLS)))
    assert col == 3


def test_blocks_immediate_loss():
    """Opponent has three in a row; minimax must block."""
    board = empty_board()
    board[ROWS - 1, 0] = 2
    board[ROWS - 1, 1] = 2
    board[ROWS - 1, 2] = 2
    agent = MinimaxAgent(depth=3, seed=0)
    col = agent.select(board, my_id=1, valid=list(range(COLS)))
    assert col == 3


def test_prefers_center_on_empty_board():
    """First move should be the center column (proven optimal start)."""
    board = empty_board()
    agent = MinimaxAgent(depth=4, seed=0)
    col = agent.select(board, my_id=1, valid=list(range(COLS)))
    assert col == COLS // 2


def test_minimax_beats_random_overwhelmingly():
    """Depth-3 minimax must dominate random play."""
    from pefforza.agent.evaluate import evaluate, random_agent

    res = evaluate(minimax_agent(depth=3, seed=0), random_agent(seed=1), games=20, seed=42)
    assert res.wins >= 18, str(res)


def test_minimax_beats_heuristic_majority():
    """Depth-4 minimax must beat the 1-ply heuristic over a meaningful sample."""
    from pefforza.agent.evaluate import evaluate, heuristic_agent

    res = evaluate(minimax_agent(depth=4, seed=0), heuristic_agent(seed=1), games=20, seed=42)
    # Generous slack: heuristic occasionally wins by exploiting tactical
    # second-player tricks. Beating it >=70% over 20 games is comfortable.
    assert res.wins >= 14, str(res)


def test_impossible_agent_is_responsive():
    """Time-budgeted search must respect roughly the configured budget."""
    board = empty_board()
    agent_cb = impossible_agent(time_budget=0.5, seed=0)
    start = time.perf_counter()
    col = agent_cb(board, my_id=1, valid=list(range(COLS)))
    elapsed = time.perf_counter() - start
    assert 0 <= col < COLS
    # The first call from an empty board does iterative deepening; we just
    # make sure we don't blow past the budget by a huge margin.
    assert elapsed < 5.0, f"impossible_agent took {elapsed:.2f}s, expected <5s"


def test_evaluate_position_is_symmetric_on_empty_board():
    board = empty_board()
    s1 = evaluate_position(board, 1)
    s2 = evaluate_position(board, 2)
    # Both players see the same empty board, so static evals must match.
    assert s1 == s2


def test_evaluate_position_rewards_center_control():
    board = empty_board()
    board[ROWS - 1, COLS // 2] = 1
    score_p1 = evaluate_position(board, 1)
    assert score_p1 > 0


def test_search_returns_metadata():
    agent = MinimaxAgent(depth=3, seed=0)
    result = agent.search(empty_board(), my_id=1, depth=3)
    assert 0 <= result.column < COLS
    assert result.depth == 3
    assert result.nodes > 0
    assert result.elapsed >= 0
    # Score on an empty board, depth 3, should be a finite heuristic value.
    assert isinstance(result.score, int)


def test_undoes_moves_during_search():
    """Search must not mutate the input board."""
    board = empty_board()
    board[ROWS - 1, 0] = 1
    board[ROWS - 1, 6] = 2
    snapshot = board.copy()
    MinimaxAgent(depth=3, seed=0).search(board, my_id=1, depth=3)
    np.testing.assert_array_equal(board, snapshot)


def test_root_does_not_treat_fail_low_bounds_as_exact_ties():
    """Depth-6 empty-board search must keep the center for every seed.

    Regression for the old root implementation, which accumulated fail-low
    alpha-beta bounds as if they were exact ties and then chose randomly among
    them. At depth 6 this made some seeds leave the proven-best center move.
    """
    board = empty_board()
    for seed in range(5):
        agent = MinimaxAgent(depth=6, seed=seed)
        assert agent.select(board, my_id=1, valid=list(range(COLS))) == COLS // 2


def test_mate_score_is_relative_to_requested_search_depth():
    """Iterative depths must not derive mate distance from ``self.depth``."""
    board = empty_board()
    board[ROWS - 1, 0] = 1
    board[ROWS - 1, 1] = 1
    board[ROWS - 1, 2] = 1

    # Configured depth intentionally differs from the requested search depth.
    result = MinimaxAgent(depth=2, seed=0).search(board, my_id=1, depth=8)
    assert result.column == 3
    assert result.score == 99_999  # mate in one from the root


def test_time_budget_is_a_real_deadline_and_reports_total_elapsed():
    board = empty_board()
    agent = MinimaxAgent(depth=4, seed=0)
    start = time.perf_counter()
    result = agent.search_with_time_budget(
        board,
        my_id=1,
        time_budget=0.05,
        min_depth=5,
        max_depth=12,
    )
    wall = time.perf_counter() - start

    assert result.column == COLS // 2
    # Give CI/scheduler jitter some room while still catching the old multi-
    # second overrun behavior.
    assert wall < 0.20
    assert abs(result.elapsed - wall) < 0.03
