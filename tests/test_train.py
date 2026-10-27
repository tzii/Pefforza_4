"""Training pipeline: network, wrapper, distillation, and PPO smoke tests.

Everything runs on tiny synthetic data - no teacher file, trained model,
camera, or audio device is needed.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from pefforza.agent.evaluate import model_agent
from pefforza.agent.networks import Connect4CNN
from pefforza.agent.train import (
    FULL_COLUMN,
    SinglePlayerWrapper,
    build_training_opponent,
    distill,
    main,
    make_model,
    teacher_targets,
    train,
)
from pefforza.constants import COLS, ROWS
from pefforza.envs.connect4_env import Connect4Env

TINY = {"channels": 8, "blocks": 1, "features_dim": 32}


def test_cnn_features_shape():
    env = Connect4Env()
    net = Connect4CNN(env.observation_space, features_dim=32, channels=8, blocks=2)
    obs = torch.zeros((5, ROWS, COLS))
    obs[:, ROWS - 1, 3] = 1
    assert net(obs).shape == (5, 32)


def test_teacher_targets_spread_over_optimal_columns():
    scores = np.array(
        [[-2, -1, 0, 1, 0, -1, -2], [FULL_COLUMN, 3, 3, -1, 0, 0, FULL_COLUMN]], np.int8
    )
    policy, values = teacher_targets(scores)
    np.testing.assert_allclose(policy[0], [0, 0, 0, 1, 0, 0, 0])
    np.testing.assert_allclose(policy[1], [0, 0.5, 0.5, 0, 0, 0, 0])
    np.testing.assert_array_equal(values, [1, 1])
    _, drawn = teacher_targets(np.array([[0, -1, -2, -3, -4, -5, -6]], np.int8))
    np.testing.assert_array_equal(drawn, [0])


def _synthetic_teacher(n: int = 256, seed: int = 0):
    """Boards where exactly one column completes a vertical three for 'self'."""
    rng = np.random.default_rng(seed)
    boards = np.zeros((n, ROWS, COLS), np.int8)
    scores = np.full((n, COLS), -2, np.int8)
    for i in range(n):
        col = int(rng.integers(COLS))
        boards[i, ROWS - 3 :, col] = 1
        other = (col + 3) % COLS
        boards[i, ROWS - 3 :, other] = 2
        scores[i, col] = 18
    return boards, scores


def test_distill_learns_and_reports_metrics():
    torch.manual_seed(0)
    model = make_model(seed=0, **TINY)
    boards, scores = _synthetic_teacher()
    metrics = distill(model, boards, scores, epochs=25, batch_size=64, lr=3e-3, val_fraction=0.1)
    assert set(metrics) == {"loss", "accuracy", "value_preserving"}
    assert metrics["accuracy"] >= 0.8

    agent = model_agent(model)
    board = boards[0].copy()
    win_col = int(np.argmax(scores[0]))
    assert agent(board, 1, list(range(COLS))) == win_col
    # Masking: a full column is never chosen even if the policy likes it.
    assert agent(board, 1, [c for c in range(COLS) if c != win_col]) != win_col


def test_distilled_model_round_trips_through_save_and_load(tmp_path):
    from stable_baselines3 import PPO

    model = make_model(seed=0, **TINY)
    boards, scores = _synthetic_teacher(64)
    distill(model, boards, scores, epochs=1, batch_size=32)
    path = tmp_path / "m.zip"
    model.save(str(path))
    loaded = PPO.load(str(path))
    obs = boards[:3].astype(np.float32)
    np.testing.assert_array_equal(
        model.predict(obs, deterministic=True)[0], loaded.predict(obs, deterministic=True)[0]
    )


def test_wrapper_plays_both_colors_from_the_agent_perspective():
    second = SinglePlayerWrapper(Connect4Env(), seed=0, agent_first_prob=0.0)
    obs, _ = second.reset()
    assert second.agent_id == 2
    assert (obs == 2).sum() == 1 and (obs == 1).sum() == 0

    first = SinglePlayerWrapper(Connect4Env(), seed=0, agent_first_prob=1.0)
    obs, _ = first.reset()
    assert not obs.any()
    obs, reward, terminated, _, _ = first.step(3)
    assert (obs == 1).sum() == 1 and (obs == 2).sum() == 1
    assert reward == 0.0 and not terminated


def test_wrapper_scores_an_opponent_win_as_a_loss():
    def stacker(board, my_id, valid):
        return 0 if 0 in valid else valid[0]

    env = SinglePlayerWrapper(Connect4Env(), seed=0, opponent=stacker, agent_first_prob=1.0)
    env.reset()
    reward, terminated = 0.0, False
    for col in (6, 5, 6, 5):
        _, reward, terminated, _, _ = env.step(col)
        if terminated:
            break
    assert terminated and reward == -1.0


def test_training_opponents():
    for name in ("random", "heuristic", "hard"):
        agent = build_training_opponent(name, seed=0)
        assert agent(np.zeros((ROWS, COLS), np.int8), 1, list(range(COLS))) in range(COLS)
    with pytest.raises(ValueError):
        build_training_opponent("nope")


def test_ppo_train_and_fine_tune_smoke(tmp_path):
    ppo = {"n_steps": 32, "batch_size": 32, "n_epochs": 1}
    final = train(timesteps=32, iterations=1, log_dir=None, models_dir=tmp_path, seed=0, **ppo)
    assert final.with_suffix(".zip").exists()
    tuned = train(
        timesteps=32,
        iterations=1,
        log_dir=None,
        models_dir=tmp_path / "tuned",
        seed=0,
        opponent="heuristic",
        init=final.with_suffix(".zip"),
        **ppo,
    )
    assert tuned.with_suffix(".zip").exists()


def test_cli_distillation(tmp_path, monkeypatch):
    import pefforza.agent.train as train_module

    boards, scores = _synthetic_teacher(64)
    data = tmp_path / "teacher.npz"
    np.savez(data, boards=boards, scores=scores)
    monkeypatch.setattr(train_module, "make_model", lambda seed=None: make_model(seed=seed, **TINY))
    out = tmp_path / "out.zip"
    main(["--teacher", str(data), "--epochs", "1", "--out", str(out), "--seed", "1"])
    assert out.exists()
