"""Difficulty tier registry shared by CLI, GUI, and physical entrypoints."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pefforza.agent.evaluate import (
    Agent,
    heuristic_agent,
    model_agent,
    random_agent,
)
from pefforza.agent.minimax import impossible_agent, minimax_agent
from pefforza.constants import DEFAULT_MODEL_PATH

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Difficulty:
    name: str
    description: str
    factory: Callable[..., Agent]


# The neural tier needs the model path at build time, so it's handled
# separately in :func:`build_opponent`.
DIFFICULTIES: dict[str, Difficulty] = {
    "easy": Difficulty(
        "easy",
        "Random opponent. Picks any legal column.",
        random_agent,
    ),
    "medium": Difficulty(
        "medium",
        "1-ply heuristic: win-if-you-can, block-if-you-must, prefer center.",
        heuristic_agent,
    ),
    "hard": Difficulty(
        "hard",
        "Minimax depth 5 with alpha-beta pruning. Sees several moves ahead.",
        lambda seed=None: minimax_agent(depth=5, seed=seed),
    ),
    "impossible": Difficulty(
        "impossible",
        (
            "Corrected iterative-deepening minimax (~3s deadline, depth 5-10). "
            "Strong heuristic search."
        ),
        lambda seed=None: impossible_agent(time_budget=3.0, seed=seed),
    ),
}

DIFFICULTY_NAMES: tuple[str, ...] = (*DIFFICULTIES.keys(), "neural")
DEFAULT_DIFFICULTY = "hard"


def build_opponent(
    name: str,
    seed: int | None = None,
    model_path: Path | None = None,
) -> Agent:
    """Return an agent callable for the requested difficulty.

    Falls back to the heuristic agent if ``neural`` is requested but the model
    cannot be loaded — the game stays playable instead of crashing.
    """
    name = name.lower()
    if name in DIFFICULTIES:
        return DIFFICULTIES[name].factory(seed=seed)

    if name == "neural":
        path = Path(model_path or DEFAULT_MODEL_PATH)
        try:
            from stable_baselines3 import PPO  # local import; optional dep
        except Exception as exc:  # pragma: no cover - optional dep
            logger.warning("stable-baselines3 unavailable (%s); using heuristic.", exc)
            return heuristic_agent(seed=seed)
        if not path.exists():
            logger.warning("Model not found at %s; using heuristic.", path)
            return heuristic_agent(seed=seed)
        try:
            model = PPO.load(str(path))
        except Exception as exc:
            logger.warning("Failed to load %s (%s); using heuristic.", path, exc)
            return heuristic_agent(seed=seed)
        return model_agent(model)

    raise ValueError(f"Unknown difficulty: {name!r}. Choose from {DIFFICULTY_NAMES}")


def describe_difficulties() -> str:
    rows = [f"  {d.name:<11} {d.description}" for d in DIFFICULTIES.values()]
    rows.append("  neural      Wraps the bundled PPO checkpoint. Strength depends on training.")
    return "\n".join(rows)


__all__ = [
    "DEFAULT_DIFFICULTY",
    "DIFFICULTIES",
    "DIFFICULTY_NAMES",
    "Difficulty",
    "build_opponent",
    "describe_difficulties",
]
