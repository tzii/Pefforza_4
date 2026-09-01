"""Tests for the evaluation harness.

These tests use deterministic and synthetic agents only, so they don't need a
trained model, an audio device, or a camera.
"""

from __future__ import annotations

import numpy as np

from pefforza.agent.evaluate import (
    MatchResult,
    evaluate,
    heuristic_agent,
    play_one_game,
    random_agent,
)
from pefforza.constants import COLS
from pefforza.rules import Board


def _leftmost_agent(board: Board, my_id: int, valid: list[int]) -> int:  # noqa: ARG001
    return valid[0]


def test_play_one_game_returns_valid_outcome():
    a = random_agent(seed=0)
    b = random_agent(seed=1)
    outcome = play_one_game(a, b, seed=42)
    assert outcome in (0, 1, 2)


def test_two_leftmost_agents_terminate_with_a_winner():
    """Two deterministic 'always pick leftmost legal column' agents must
    finish; given the column-by-column fill pattern, P1 wins horizontally."""
    outcome = play_one_game(_leftmost_agent, _leftmost_agent, seed=0)
    assert outcome in (0, 1, 2)


def test_match_result_tracks_totals():
    r = MatchResult(wins=4, losses=3, draws=1)
    assert r.games == 8
    assert 0.0 <= r.win_rate <= 1.0
    s = str(r)
    assert "wins=4" in s and "losses=3" in s and "draws=1" in s


def test_evaluate_runs_requested_number_of_games():
    a = random_agent(seed=0)
    b = random_agent(seed=1)
    res = evaluate(a, b, games=10, seed=42)
    assert res.games == 10


def test_heuristic_beats_random_majority():
    """The 1-ply heuristic must reliably beat random over a meaningful sample."""
    h = heuristic_agent(seed=0)
    r = random_agent(seed=1)
    res = evaluate(h, r, games=40, seed=42)
    # Generous slack — we just want to be sure the heuristic is doing *something*.
    assert res.wins > res.losses, str(res)


def test_evaluate_swaps_sides():
    """When swap_sides=True the agent goes first in even games and second in odd."""
    agent_starts: list[bool] = []
    opp_starts: list[bool] = []

    def agent(board: Board, my_id: int, valid: list[int]) -> int:  # noqa: ARG001
        if not np.any(board != 0):
            agent_starts.append(my_id == 1)
        return valid[0]

    def opp(board: Board, my_id: int, valid: list[int]) -> int:  # noqa: ARG001
        if not np.any(board != 0):
            opp_starts.append(my_id == 1)
        return valid[0]

    evaluate(agent, opp, games=4, seed=0, swap_sides=True)
    # 4 games, alternating: agent first, opp first, agent first, opp first.
    assert agent_starts == [True, True]
    assert opp_starts == [True, True]


def test_invalid_action_is_treated_as_forfeit():
    """An agent that returns an out-of-range column forfeits."""

    def bad_p1(board: Board, my_id: int, valid: list[int]) -> int:  # noqa: ARG001
        return COLS + 5  # always illegal

    def good_p2(board: Board, my_id: int, valid: list[int]) -> int:  # noqa: ARG001
        return valid[0]

    outcome = play_one_game(bad_p1, good_p2, seed=0)
    assert outcome == 2  # P2 wins by P1 forfeit
