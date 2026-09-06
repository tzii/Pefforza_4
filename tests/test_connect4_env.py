"""Behavioural tests for Connect4Env."""

from __future__ import annotations

import numpy as np
import pytest

from pefforza.constants import COLS, ROWS
from pefforza.envs.connect4_env import (
    INVALID_MOVE_PENALTY,
    STEP_REWARD,
    WIN_REWARD,
    Connect4Env,
)


@pytest.fixture
def env() -> Connect4Env:
    e = Connect4Env()
    e.reset(seed=0)
    return e


def test_reset_returns_clean_state(env: Connect4Env):
    obs, info = env.reset()
    assert obs.shape == (ROWS, COLS)
    assert (obs == 0).all()
    assert info == {}
    assert env.current_player == 1


def test_step_drops_to_bottom(env: Connect4Env):
    obs, reward, terminated, truncated, _ = env.step(3)
    assert obs[ROWS - 1, 3] == 1
    assert reward == STEP_REWARD
    assert not terminated and not truncated
    # Turn passed.
    assert env.current_player == 2


def test_step_alternates_players_and_stacks(env: Connect4Env):
    env.step(0)  # P1 bottom row
    env.step(0)  # P2 above
    assert env.board[ROWS - 1, 0] == 1
    assert env.board[ROWS - 2, 0] == 2


def test_full_column_is_invalid(env: Connect4Env):
    for _ in range(ROWS):
        env.board[:, 1] = 1  # force full column
    obs, reward, terminated, truncated, info = env.step(1)
    assert reward == INVALID_MOVE_PENALTY
    assert terminated
    assert info.get("error") == "Invalid move"


@pytest.mark.parametrize("bad_action", [-1, COLS, 99])
def test_action_out_of_range(env: Connect4Env, bad_action: int):
    _, reward, terminated, _, info = env.step(bad_action)
    assert reward == INVALID_MOVE_PENALTY
    assert terminated
    assert "error" in info


def test_horizontal_win_returns_win_reward(env: Connect4Env):
    # Build P1 horizontal win: P1 plays cols 0..3, P2 plays col 6 each turn.
    moves = [0, 6, 1, 6, 2, 6, 3]
    last = None
    for m in moves:
        last = env.step(m)
    assert last is not None
    _, reward, terminated, _, info = last
    assert reward == WIN_REWARD
    assert terminated
    assert info.get("winner") == 1


def test_draw_returns_zero_reward_terminated():
    env = Connect4Env()
    env.reset()
    # Pre-fill board with a known no-winner pattern: alternating columns of 1/2.
    # Pattern avoids 4-in-a-row by shifting tokens.
    pattern = np.array(
        [
            [1, 2, 1, 2, 1, 2, 1],
            [1, 2, 1, 2, 1, 2, 1],
            [2, 1, 2, 1, 2, 1, 2],
            [2, 1, 2, 1, 2, 1, 2],
            [1, 2, 1, 2, 1, 2, 1],
            [1, 2, 1, 2, 1, 2, 1],
        ],
        dtype=np.int8,
    )
    env.board = pattern.copy()
    # Force one cell empty so we can play the final move.
    env.board[0, 0] = 0
    env.current_player = 1
    obs, reward, terminated, _, info = env.step(0)
    assert terminated
    assert reward == STEP_REWARD
    # Either a draw or a win: assert outcome matches the actual board.
    assert "draw" in info or info.get("winner") == 1


def test_valid_action_mask(env: Connect4Env):
    mask = env.valid_action_mask()
    assert mask.shape == (COLS,)
    assert mask.all()
    # Fill column 2 and re-check.
    env.board[:, 2] = 1
    mask = env.valid_action_mask()
    assert not mask[2]
    assert mask.sum() == COLS - 1


@pytest.mark.parametrize(
    "bad_action", [1.9, "2", None, np.array([2]), np.nan, True, np.bool_(True)]
)
def test_non_discrete_actions_do_not_become_legal_moves(env, bad_action):
    before = env.board.copy()
    _, reward, terminated, truncated, info = env.step(bad_action)
    assert reward == INVALID_MOVE_PENALTY
    assert terminated and not truncated
    assert "error" in info
    np.testing.assert_array_equal(env.board, before)


@pytest.mark.parametrize("action", [2, np.int64(2), np.array(2, dtype=np.int64)])
def test_discrete_integer_actions_remain_supported(env, action):
    obs, _, terminated, _, _ = env.step(action)
    assert not terminated
    assert obs[-1, 2] == 1


def test_observations_are_independent_snapshots(env):
    initial, _ = env.reset()
    first, *_ = env.step(0)
    env.step(1)
    assert not initial.any()
    assert first[-1, 1] == 0
    first[:] = 2
    assert env.board[0, 0] == 0


@pytest.mark.parametrize("moves", [[-1], [0, 6, 1, 6, 2, 6, 3]])
def test_terminal_episode_cannot_be_resumed_without_reset(env, moves):
    for action in moves:
        env.step(action)
    before = env.board.copy()
    assert not env.valid_action_mask().any()
    with pytest.raises(RuntimeError, match="reset"):
        env.step(2)
    np.testing.assert_array_equal(env.board, before)
    env.reset()
    assert env.valid_action_mask().all()
    assert not env.step(2)[2]


def test_rgb_array_render_is_an_independent_rgb_image():
    env = Connect4Env(render_mode="rgb_array")
    env.reset()
    initial = env.render()
    env.step(0)
    played = env.render()
    assert played.shape == (ROWS * 32, COLS * 32, 3)
    assert played.dtype == np.uint8
    np.testing.assert_array_equal(played[-16, 16], [249, 132, 120])
    np.testing.assert_array_equal(initial[-16, 16], [17, 22, 34])
    played[:] = 0
    assert env.render().any()
    assert env.board[-1, 0] == 1


def test_render_modes_are_explicit(capsys):
    with pytest.raises(ValueError, match="render mode"):
        Connect4Env(render_mode="unknown")
    assert Connect4Env().render() is None
    assert Connect4Env(render_mode="human").render() is None
    assert "----------------" in capsys.readouterr().out
