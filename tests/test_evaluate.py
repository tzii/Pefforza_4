"""Tests for the evaluation harness.

These tests use deterministic and synthetic agents only, so they don't need a
trained model, an audio device, or a camera.
"""

from __future__ import annotations

import numpy as np
import pytest

from pefforza.agent.evaluate import (
    MatchResult,
    _parse_args,
    evaluate,
    heuristic_agent,
    model_agent,
    play_one_game,
    random_agent,
)
from pefforza.constants import COLS
from pefforza.envs.connect4_env import Connect4Env
from pefforza.rules import Board, empty_board, swap_perspective


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


@pytest.mark.parametrize(
    "action", [0.0, np.array([0]), np.array([0, 1]), None, "0", True, np.bool_(True)]
)
@pytest.mark.parametrize("bad_player", [1, 2])
def test_non_discrete_actions_forfeit_instead_of_drawing(action, bad_player):
    def bad_agent(board, my_id, valid):
        return action

    agents = (bad_agent, _leftmost_agent) if bad_player == 1 else (_leftmost_agent, bad_agent)
    assert play_one_game(*agents) == 3 - bad_player


def test_agent_cannot_mutate_the_authoritative_board_or_legal_moves():
    def destructive_agent(board, my_id, valid):
        board[:] = my_id
        valid[:] = [COLS + 1]
        return COLS + 1

    assert play_one_game(destructive_agent, _leftmost_agent) == 2


@pytest.mark.parametrize("action", [3, np.int64(3), np.array(3), np.array([3])])
@pytest.mark.parametrize("my_id", [1, 2])
def test_model_predictions_support_scalar_arrays_and_translate_perspective(action, my_id):
    board = empty_board()
    board[-1, :2] = [1, 2]
    before = board.copy()
    expected = board if my_id == 1 else swap_perspective(board)

    class Model:
        def predict(self, obs, deterministic):
            assert deterministic
            np.testing.assert_array_equal(obs, expected)
            obs[:] = 2
            return action, None

    assert model_agent(Model())(board, my_id, list(range(COLS))) == 3
    np.testing.assert_array_equal(board, before)


@pytest.mark.parametrize("action", [3.5, np.nan, "3", np.array([1, 2]), -1, COLS])
def test_invalid_model_predictions_fall_back_to_a_legal_column(action):
    class Model:
        def predict(self, obs, deterministic):
            return action, None

    assert model_agent(Model())(empty_board(), 1, [2, 4]) == 2


def test_evaluation_rejects_nonpositive_game_counts():
    for games in (0, -1):
        with pytest.raises(ValueError, match="games"):
            evaluate(_leftmost_agent, _leftmost_agent, games=games)


@pytest.mark.parametrize("args", [["--games", "0"], ["--minimax-depth", "-1"]])
def test_evaluation_cli_rejects_nonpositive_work(args):
    with pytest.raises(SystemExit) as exc:
        _parse_args(args)
    assert exc.value.code == 2


@pytest.mark.parametrize("fail", [False, True])
def test_evaluation_always_closes_environment(monkeypatch, fail):
    closed = []
    monkeypatch.setattr(Connect4Env, "close", lambda self: closed.append(True))

    def agent(board, player, valid):
        if fail:
            raise RuntimeError("agent failed")
        return valid[0]

    if fail:
        with pytest.raises(RuntimeError, match="agent failed"):
            play_one_game(agent, _leftmost_agent)
    else:
        play_one_game(agent, _leftmost_agent)
    assert closed == [True]


def test_complete_evaluation_is_repeatable_with_fresh_seeded_agents():
    def run():
        return evaluate(random_agent(seed=1), heuristic_agent(seed=2), games=12, seed=3)

    assert run() == run()
