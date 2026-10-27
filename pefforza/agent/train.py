"""Training for the ``neural`` tier: solver distillation and PPO fine-tuning.

Two complementary modes, both producing ordinary Stable-Baselines3 ``PPO``
checkpoints that the ``neural`` tier loads unchanged:

* **Distillation** (``--teacher data.npz``) - supervised learning from exact
  solver labels (``scripts/build_teacher_set.py``): the policy learns the
  distribution over optimal columns, the value head the game-theoretic
  outcome. This is what the bundled checkpoint is trained with.
* **PPO** (default) - reinforcement learning against an opponent through
  :class:`SinglePlayerWrapper`, which plays both colors and always shows the
  agent its own perspective (``1 = self``). Use ``--init`` to fine-tune a
  distilled model.

Examples::

    python -m pefforza.agent.train --teacher teacher.npz --epochs 12 --out model.zip
    python -m pefforza.agent.train --init model.zip --opponent heuristic --timesteps 200000
"""

from __future__ import annotations

import argparse
import logging
import random
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.preprocessing import preprocess_obs
from torch.nn import functional as F  # noqa: N812

from pefforza.agent.evaluate import Agent, heuristic_agent, random_agent
from pefforza.agent.networks import Connect4CNN
from pefforza.envs.connect4_env import Connect4Env
from pefforza.rules import available_columns, swap_perspective

logger = logging.getLogger(__name__)

FULL_COLUMN = -128  # marker for full columns in teacher score arrays


class SinglePlayerWrapper(gym.Wrapper):
    """Turn the two-player env into a single-agent one against ``opponent``.

    Each episode the agent plays first with probability ``agent_first_prob``
    (otherwise the opponent opens), and observations are always from the
    agent's perspective: ``1 = agent``, ``2 = opponent``. Rewards: +1 win,
    -1 loss, 0 draw; an illegal agent move keeps the env's penalty.
    """

    # The wrapped env is always our concrete Connect4Env; type-hint that so
    # mypy and IDEs see ``self.env.board`` and ``.cols`` correctly.
    env: Connect4Env

    def __init__(
        self,
        env: Connect4Env,
        seed: int | None = None,
        opponent: Agent | None = None,
        agent_first_prob: float = 0.5,
    ) -> None:
        super().__init__(env)
        self._rng = random.Random(seed)
        self.opponent = opponent if opponent is not None else random_agent(seed=seed)
        self.agent_first_prob = agent_first_prob
        self.agent_id = 1

    def _observe(self) -> np.ndarray:
        board = self.env.board
        return board.copy() if self.agent_id == 1 else swap_perspective(board)

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        _, info = self.env.reset(seed=seed, options=options)
        self.agent_id = 1 if self._rng.random() < self.agent_first_prob else 2
        if self.agent_id == 2:
            self._opponent_move()
        return self._observe(), info

    def _opponent_move(self) -> tuple[float, bool, bool, dict[str, Any]]:
        valid = available_columns(self.env.board)
        action = self.opponent(self.env.board, self.env.current_player, valid)
        if action not in valid:
            action = valid[0]
        _, reward, terminated, truncated, info = self.env.step(action)
        return reward, terminated, truncated, info

    def step(self, action):
        _, reward, terminated, truncated, info = self.env.step(action)
        if terminated or truncated:
            return self._observe(), reward, terminated, truncated, info
        if not available_columns(self.env.board):
            return self._observe(), 0.0, True, False, {"draw": True}

        opp_reward, terminated, truncated, info = self._opponent_move()
        # The opponent winning is a loss for the agent.
        reward = -1.0 if terminated and opp_reward == 1.0 else 0.0
        return self._observe(), reward, terminated, truncated, info


OPPONENTS = ("random", "heuristic", "hard")


def build_training_opponent(name: str, seed: int | None = None) -> Agent:
    if name == "random":
        return random_agent(seed=seed)
    if name == "heuristic":
        return heuristic_agent(seed=seed)
    if name == "hard":
        from pefforza.agent.difficulty import bitboard_agent

        return bitboard_agent(depth=4)
    raise ValueError(f"unknown opponent {name!r}; choose from {OPPONENTS}")


def make_model(
    env: gym.Env | None = None,
    *,
    channels: int = 64,
    blocks: int = 4,
    features_dim: int = 256,
    seed: int | None = None,
    **ppo_kwargs: Any,
) -> PPO:
    """A PPO model with the :class:`Connect4CNN` trunk shared by both heads."""
    if env is None:
        env = SinglePlayerWrapper(Connect4Env(), seed=seed)
    policy_kwargs = {
        "features_extractor_class": Connect4CNN,
        "features_extractor_kwargs": {
            "channels": channels,
            "blocks": blocks,
            "features_dim": features_dim,
        },
        "net_arch": {"pi": [features_dim], "vf": [features_dim]},
        "share_features_extractor": True,
    }
    return PPO("MlpPolicy", env, policy_kwargs=policy_kwargs, seed=seed, **ppo_kwargs)


# ------------------------------------------------------------ distillation
def teacher_targets(scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Soft policy targets and outcome values from exact column scores.

    The policy target is uniform over the exactly optimal columns (fastest
    win / slowest loss / any drawing move) and zero elsewhere - including
    full columns, so the network also learns legality. The value target is
    the game-theoretic outcome for the side to move: +1, 0 or -1.
    """
    scores = scores.astype(np.int16)
    legal = scores != FULL_COLUMN
    masked = np.where(legal, scores, np.iinfo(np.int16).min)
    best = masked.max(axis=1, keepdims=True)
    optimal = (masked == best) & legal
    policy = optimal / optimal.sum(axis=1, keepdims=True)
    values = np.sign(best[:, 0]).astype(np.float32)
    return policy.astype(np.float32), values


def _policy_outputs(model: PPO, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    policy = model.policy
    features = policy.features_extractor(
        preprocess_obs(obs, policy.observation_space, normalize_images=policy.normalize_images)
    )
    latent_pi, latent_vf = policy.mlp_extractor(features)
    return policy.action_net(latent_pi), policy.value_net(latent_vf).squeeze(-1)


def distill(
    model: PPO,
    boards: np.ndarray,
    scores: np.ndarray,
    *,
    epochs: int = 10,
    batch_size: int = 512,
    lr: float = 1e-3,
    value_weight: float = 0.5,
    val_fraction: float = 0.05,
    mirror: bool = True,
    seed: int = 0,
) -> dict[str, float]:
    """Supervised training of ``model``'s policy and value heads in place.

    ``boards`` (N, 6, 7) are from the mover's perspective, ``scores`` (N, 7)
    exact column scores with :data:`FULL_COLUMN` for full columns. Mirror
    images are added when ``mirror`` is set (Connect Four is left-right
    symmetric). Returns validation metrics: ``accuracy`` (argmax among legal
    columns is exactly optimal), ``value_preserving`` (it keeps the game
    outcome) and ``loss``.
    """
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(boards))
    n_val = max(1, int(len(boards) * val_fraction))
    val_idx, train_idx = order[:n_val], order[n_val:]

    train_boards, train_scores = boards[train_idx], scores[train_idx]
    if mirror:
        train_boards = np.concatenate([train_boards, train_boards[:, :, ::-1]])
        train_scores = np.concatenate([train_scores, train_scores[:, ::-1]])
    train_policy, train_values = teacher_targets(train_scores)
    val_scores = scores[val_idx].astype(np.int16)

    obs_t = torch.as_tensor(np.ascontiguousarray(train_boards), dtype=torch.float32)
    pol_t = torch.as_tensor(train_policy)
    val_t = torch.as_tensor(train_values)
    val_obs = torch.as_tensor(np.ascontiguousarray(boards[val_idx]), dtype=torch.float32)

    policy = model.policy
    optimizer = torch.optim.AdamW(policy.parameters(), lr=lr, weight_decay=1e-4)
    steps = epochs * ((len(obs_t) + batch_size - 1) // batch_size)
    schedule = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=lr, total_steps=steps)
    gen = torch.Generator().manual_seed(seed)
    metrics: dict[str, float] = {}
    for epoch in range(1, epochs + 1):
        policy.set_training_mode(True)
        perm = torch.randperm(len(obs_t), generator=gen)
        total = 0.0
        for start in range(0, len(obs_t), batch_size):
            idx = perm[start : start + batch_size]
            logits, value = _policy_outputs(model, obs_t[idx])
            loss = -(pol_t[idx] * F.log_softmax(logits, dim=-1)).sum(-1).mean()
            loss = loss + value_weight * F.mse_loss(torch.tanh(value), val_t[idx])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            schedule.step()
            total += loss.item() * len(idx)
        metrics = {"loss": total / len(obs_t), **_validate(model, val_obs, val_scores)}
        logger.info(
            "epoch %d/%d  loss %.4f  val optimal %.1f%%  val value-preserving %.1f%%",
            epoch,
            epochs,
            metrics["loss"],
            100 * metrics["accuracy"],
            100 * metrics["value_preserving"],
        )
    policy.set_training_mode(False)
    # Keep checkpoints small: SB3 saves the optimizer state with the policy,
    # and distillation's AdamW moments are useless for later PPO training.
    policy.optimizer = policy.optimizer_class(  # type: ignore[call-arg]
        policy.parameters(), lr=model.lr_schedule(1.0), **policy.optimizer_kwargs
    )
    return metrics


def _validate(model: PPO, obs: torch.Tensor, scores: np.ndarray) -> dict[str, float]:
    model.policy.set_training_mode(False)
    with torch.no_grad():
        logits, _ = _policy_outputs(model, obs)
    legal = scores != FULL_COLUMN
    masked = logits.numpy()
    masked[~legal] = -np.inf
    choice = masked.argmax(axis=1)
    chosen = scores[np.arange(len(scores)), choice]
    best = np.where(legal, scores, -1000).max(axis=1)
    return {
        "accuracy": float((chosen == best).mean()),
        "value_preserving": float((np.sign(chosen) == np.sign(best)).mean()),
    }


# ---------------------------------------------------------------------- PPO
def train(
    timesteps: int = 10_000,
    iterations: int = 5,
    log_dir: Path | str | None = "pefforza/agent/logs",
    models_dir: Path | str = "pefforza/agent/models",
    seed: int | None = None,
    opponent: str = "random",
    init: Path | str | None = None,
    **ppo_kwargs: Any,
) -> Path:
    """PPO training (or fine-tuning ``init``); returns the final model path."""
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    env = SinglePlayerWrapper(
        Connect4Env(), seed=seed, opponent=build_training_opponent(opponent, seed=seed)
    )
    tb_log = None
    if log_dir is not None:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        tb_log = str(log_dir)
    if init is not None:
        model = PPO.load(str(init), env=env, tensorboard_log=tb_log, seed=seed, **ppo_kwargs)
    else:
        model = make_model(env, seed=seed, tensorboard_log=tb_log, verbose=1, **ppo_kwargs)

    for i in range(1, iterations + 1):
        model.learn(total_timesteps=timesteps, reset_num_timesteps=False, tb_log_name="PPO")
        ckpt = models_dir / f"ppo_connect4_{timesteps * i}"
        model.save(str(ckpt))
        logger.info("Saved checkpoint: %s", ckpt)

    final = models_dir / "ppo_connect4"
    model.save(str(final))
    logger.info("Saved final model: %s", final)
    return final


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--teacher", type=Path, default=None, help="Distill from this .npz set.")
    p.add_argument("--epochs", type=int, default=10, help="Distillation epochs.")
    p.add_argument("--batch-size", type=int, default=512)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--out", type=Path, default=Path("pefforza/agent/models/distilled.zip"))
    p.add_argument("--timesteps", type=int, default=10_000, help="PPO steps per iteration.")
    p.add_argument("--iterations", type=int, default=5)
    p.add_argument("--opponent", choices=OPPONENTS, default="random")
    p.add_argument("--init", type=Path, default=None, help="Fine-tune this checkpoint.")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--log-dir", default="pefforza/agent/logs")
    p.add_argument("--models-dir", default="pefforza/agent/models")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    if args.teacher is not None:
        data = np.load(args.teacher)
        model = make_model(seed=args.seed)
        torch.manual_seed(args.seed or 0)
        metrics = distill(
            model,
            data["boards"],
            data["scores"],
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            seed=args.seed or 0,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(args.out))
        logger.info("Saved distilled model to %s (%s)", args.out, metrics)
        return
    train(
        timesteps=args.timesteps,
        iterations=args.iterations,
        log_dir=args.log_dir,
        models_dir=args.models_dir,
        seed=args.seed,
        opponent=args.opponent,
        init=args.init,
    )


if __name__ == "__main__":
    main()
