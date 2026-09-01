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
from pefforza.agent.minimax import (
    impossible_agent,
    tactical_safety_net,
)
from pefforza.agent.search import BitboardSearchAgent
from pefforza.constants import DEFAULT_MODEL_PATH

logger = logging.getLogger(__name__)

# Search depth of the bitboard `hard` backend. Depth 8 keeps a move well
# under ~50 ms on commodity hardware (see scripts/benchmark_search.py) so the
# GUI stays responsive without a worker thread; the matrix baseline needed
# for comparison remains available via pefforza.agent.minimax.
HARD_BITBOARD_DEPTH = 8


@dataclass(frozen=True)
class Difficulty:
    name: str
    description: str
    factory: Callable[..., Agent]


def bitboard_agent(depth: int = HARD_BITBOARD_DEPTH, seed: int | None = None) -> Agent:
    """Bitboard alpha-beta agent - the ``hard`` backend.

    Same heuristic semantics as the matrix engine (pinned by the differential
    tests in ``tests/test_bitboard_search.py``) at a fraction of the cost,
    thanks to integer board operations and a transposition table. The engine
    is deterministic; ``seed`` is accepted for registry uniformity and ignored.
    """
    engine = BitboardSearchAgent(depth=depth, use_tt=True)
    return tactical_safety_net(engine.select)


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
        (
            f"Bitboard alpha-beta search, depth {HARD_BITBOARD_DEPTH} (same heuristic "
            "as the matrix baseline, an order of magnitude faster)."
        ),
        bitboard_agent,
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
    "HARD_BITBOARD_DEPTH",
    "bitboard_agent",
    "build_opponent",
    "describe_difficulties",
]
