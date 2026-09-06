"""Training contracts without fitting or loading a neural model."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pefforza.agent import train as training
from pefforza.agent.train import SinglePlayerWrapper
from pefforza.envs.connect4_env import INVALID_MOVE_PENALTY, Connect4Env


def test_seeded_reset_replays_the_same_opponent_moves():
    env = SinglePlayerWrapper(Connect4Env(), seed=0)

    def rollout():
        env.reset(seed=42)
        return [env.step(action)[0] for action in (3, 2, 4)]

    first, second = rollout(), rollout()
    for before, after in zip(first, second, strict=True):
        np.testing.assert_array_equal(before, after)


def test_unseeded_reset_preserves_the_opponent_rng_stream():
    env = SinglePlayerWrapper(Connect4Env(), seed=7)
    env.reset(seed=42)
    env.step(3)
    state = env._rng.getstate()
    env.reset()
    assert env._rng.getstate() == state


@pytest.mark.parametrize("invalid_action", [-1, 0.0])
def test_invalid_agent_action_ends_without_an_opponent_move(invalid_action):
    env = SinglePlayerWrapper(Connect4Env(), seed=0)
    env.reset()
    obs, reward, terminated, truncated, info = env.step(invalid_action)
    assert terminated and not truncated
    assert reward == INVALID_MOVE_PENALTY
    assert "error" in info
    assert not obs.any()


def test_agent_win_does_not_allow_an_opponent_reply():
    env = SinglePlayerWrapper(Connect4Env(), seed=0)
    env.reset()
    env.env.board[-1, :3] = 1
    env.env.board[-1, 4:] = 2
    obs, reward, terminated, truncated, info = env.step(3)
    assert (reward, terminated, truncated, info) == (1.0, True, False, {"winner": 1})
    assert np.count_nonzero(obs) == 7


def test_opponent_win_is_a_loss_for_the_training_agent():
    env = SinglePlayerWrapper(Connect4Env(), seed=0)
    env.reset()
    env.env.board[-3:, 6] = 2
    # The seeded opponent's first random legal choice is column 6.
    obs, reward, terminated, truncated, info = env.step(3)
    assert (reward, terminated, truncated, info) == (-1.0, True, False, {"winner": 2})
    assert np.count_nonzero(obs == 1) == 1


@pytest.mark.parametrize("kwargs", [{"timesteps": 0}, {"iterations": 0}, {"iterations": -1}])
def test_training_rejects_empty_runs_before_creating_output(tmp_path, kwargs):
    output = tmp_path / "unused"
    with pytest.raises(ValueError, match="positive"):
        training.train(log_dir=output, models_dir=output, **kwargs)
    assert not output.exists()


@pytest.mark.parametrize("args", [["--timesteps", "0"], ["--iterations", "-1"]])
def test_training_cli_rejects_nonpositive_work(args):
    with pytest.raises(SystemExit) as exc:
        training._parse_args(args)
    assert exc.value.code == 2


def test_training_closes_environment_when_learning_fails(monkeypatch, tmp_path):
    closed = []
    monkeypatch.setattr(Connect4Env, "close", lambda self: closed.append(True))

    class FailingModel:
        def __init__(self, *args, **kwargs):
            pass

        def learn(self, **kwargs):
            raise RuntimeError("training failed")

    monkeypatch.setattr(training, "PPO", FailingModel)
    with pytest.raises(RuntimeError, match="training failed"):
        training.train(timesteps=1, iterations=1, log_dir=tmp_path, models_dir=tmp_path)
    assert closed == [True]


def test_training_returns_the_written_checkpoint_and_closes_environment(monkeypatch, tmp_path):
    closed = []
    learns = []
    monkeypatch.setattr(Connect4Env, "close", lambda self: closed.append(True))

    class Model:
        def __init__(self, *args, **kwargs):
            pass

        def learn(self, **kwargs):
            learns.append(kwargs)

        def save(self, path):
            Path(path).with_suffix(".zip").touch()

    monkeypatch.setattr(training, "PPO", Model)
    final = training.train(timesteps=4, iterations=2, log_dir=tmp_path, models_dir=tmp_path)
    assert final == tmp_path / "ppo_connect4.zip"
    assert final.is_file()
    assert (tmp_path / "ppo_connect4_4.zip").is_file()
    assert (tmp_path / "ppo_connect4_8.zip").is_file()
    assert (
        learns == [{"total_timesteps": 4, "reset_num_timesteps": False, "tb_log_name": "PPO"}] * 2
    )
    assert closed == [True]


def test_training_closes_environment_when_model_creation_fails(monkeypatch, tmp_path):
    closed = []
    monkeypatch.setattr(Connect4Env, "close", lambda self: closed.append(True))

    def fail(*args, **kwargs):
        raise RuntimeError("model creation failed")

    monkeypatch.setattr(training, "PPO", fail)
    with pytest.raises(RuntimeError, match="model creation failed"):
        training.train(timesteps=1, iterations=1, log_dir=tmp_path, models_dir=tmp_path)
    assert closed == [True]
