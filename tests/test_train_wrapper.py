"""Tests for the PPO training wrapper in ``pefforza.agent.train``.

``SinglePlayerWrapper`` is the reward-translation seam between the
two-player ``Connect4Env`` and single-agent SB3 training: a bug there
silently corrupts the training signal instead of crashing, so each reward
path is pinned with a hand-built board. The ``train()`` smoke run only
checks checkpoint plumbing and needs no pre-trained model.
"""

from __future__ import annotations

import numpy as np

from pefforza.agent.train import SinglePlayerWrapper, _parse_args, train
from pefforza.constants import COLS
from pefforza.envs.connect4_env import STEP_REWARD, Connect4Env
from pefforza.rules import check_winner, empty_board

# Checkerboard fill: no 4-in-a-row in any direction (verified in
# tests/test_connect4_env.py's draw test lineage).
_CHECKERBOARD = np.array(
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


def _wrapper_on(board, current_player: int = 1, seed: int = 0) -> SinglePlayerWrapper:
    env = Connect4Env()
    env.reset()
    env.board = board
    env.current_player = current_player
    return SinglePlayerWrapper(env, seed=seed)


def test_step_plays_agent_then_opponent_move():
    """A non-terminal step must drop the agent's token AND the opponent's."""
    wrapper = _wrapper_on(empty_board())
    obs, reward, terminated, truncated, _ = wrapper.step(3)
    # Two tokens per wrapper step: agent's and the random opponent's.
    assert np.count_nonzero(obs) == 2
    assert obs[5, 3] == 1
    assert reward == STEP_REWARD
    assert not terminated and not truncated
    # Both moves happened, so it is the agent's turn again.
    assert wrapper.env.current_player == 1


def test_agent_win_passthrough_without_opponent_move():
    board = empty_board()
    board[5, 2] = board[4, 2] = board[3, 2] = 1
    wrapper = _wrapper_on(board)
    obs, reward, terminated, _, info = wrapper.step(2)
    assert reward == 1.0
    assert terminated
    assert info.get("winner") == 1
    # The opponent must not get a move after the game is over.
    assert np.count_nonzero(obs) == 4


def test_opponent_win_is_reported_as_agent_loss():
    """The wrapper must flip the opponent's +1 into the agent's -1."""
    board = _CHECKERBOARD.copy()
    board[5, 3] = board[4, 3] = board[3, 3] = 2  # opponent three vertical
    board[2, 3] = board[1, 3] = board[0, 3] = 0  # open above the threat
    board[0, 0] = 0  # the agent's only safe reply fills column 0
    assert check_winner(board) == 0  # fixture sanity

    wrapper = _wrapper_on(board)
    obs, reward, terminated, _, _ = wrapper.step(0)
    assert terminated
    assert reward == -1.0
    # Column 0 was the agent's move, so the opponent's only legal column is 3.
    assert obs[2, 3] == 2


def test_board_full_after_agent_move_reports_draw():
    board = _CHECKERBOARD.copy()
    board[0, 0] = 0  # last open cell
    assert check_winner(board) == 0

    wrapper = _wrapper_on(board)
    obs, reward, terminated, _, info = wrapper.step(0)
    assert terminated
    assert reward == STEP_REWARD
    assert info.get("draw") is True
    assert np.count_nonzero(obs) == COLS * board.shape[0]


def test_parse_args_defaults():
    args = _parse_args([])
    assert args.timesteps == 10_000
    assert args.iterations == 5
    assert args.seed is None
    assert args.log_dir == "pefforza/agent/logs"
    assert args.models_dir == "pefforza/agent/models"


def test_train_smoke_saves_checkpoints(tmp_path):
    """End-to-end plumbing: a tiny PPO run must write and return checkpoints."""
    final = train(
        timesteps=24,
        iterations=1,
        log_dir=tmp_path / "logs",
        models_dir=tmp_path / "models",
        seed=0,
    )
    assert final.exists()
    assert final == tmp_path / "models" / "ppo_connect4.zip"
    assert (tmp_path / "models" / "ppo_connect4_24.zip").exists()
