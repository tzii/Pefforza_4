"""PPO self-play training entrypoint.

Wraps ``Connect4Env`` so a Stable-Baselines3 single-agent algorithm can be
used directly: the wrapper plays a (currently random) opponent move after the
agent moves and translates the opponent's reward sign into the agent's reward.
"""

from __future__ import annotations

import argparse
import logging
import random
from pathlib import Path

import gymnasium as gym
from stable_baselines3 import PPO

from pefforza.envs.connect4_env import Connect4Env
from pefforza.rules import available_columns

logger = logging.getLogger(__name__)


class SinglePlayerWrapper(gym.Wrapper):
    """Plays a random opponent move after each agent step."""

    # The wrapped env is always our concrete Connect4Env; type-hint that so
    # mypy and IDEs see ``self.env.board`` and ``.cols`` correctly.
    env: Connect4Env

    def __init__(self, env: Connect4Env, seed: int | None = None) -> None:
        super().__init__(env)
        self._rng = random.Random(seed)

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        if terminated or truncated:
            return obs, reward, terminated, truncated, info

        valid = available_columns(self.env.board)
        if not valid:
            return obs, 0.0, True, False, {"draw": True}

        opp_action = self._rng.choice(valid)
        obs, opp_reward, terminated, truncated, info = self.env.step(opp_action)
        # If the opponent won, reflect that as a loss for the agent.
        if terminated and opp_reward == 1.0:
            reward = -1.0
        return obs, reward, terminated, truncated, info


def train(
    timesteps: int = 10_000,
    iterations: int = 5,
    log_dir: Path | str = "pefforza/agent/logs",
    models_dir: Path | str = "pefforza/agent/models",
    seed: int | None = None,
) -> Path:
    """Train PPO and write checkpoints. Returns the path to the final model."""
    log_dir = Path(log_dir)
    models_dir = Path(models_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    env = SinglePlayerWrapper(Connect4Env(), seed=seed)
    model = PPO("MlpPolicy", env, verbose=1, tensorboard_log=str(log_dir), seed=seed)

    for i in range(1, iterations + 1):
        model.learn(
            total_timesteps=timesteps,
            reset_num_timesteps=False,
            tb_log_name="PPO",
        )
        ckpt = models_dir / f"ppo_connect4_{timesteps * i}"
        model.save(str(ckpt))
        logger.info("Saved checkpoint: %s", ckpt)

    final = models_dir / "ppo_connect4"
    model.save(str(final))
    logger.info("Saved final model: %s", final)
    return final


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train a PPO Connect 4 agent.")
    p.add_argument("--timesteps", type=int, default=10_000)
    p.add_argument("--iterations", type=int, default=5)
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
    train(
        timesteps=args.timesteps,
        iterations=args.iterations,
        log_dir=args.log_dir,
        models_dir=args.models_dir,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
