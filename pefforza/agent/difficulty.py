"""Difficulty tier registry shared by CLI, GUI, and physical entrypoints."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pefforza.agent.evaluate import (
    Agent,
    heuristic_agent,
    model_agent,
    random_agent,
)
from pefforza.agent.minimax import tactical_safety_net
from pefforza.agent.search import (
    BitboardSearchAgent,
    BitPosition,
    OpeningBook,
    PerfectSolver,
    default_book,
)
from pefforza.constants import DEFAULT_MODEL_PATH
from pefforza.rules import Board

logger = logging.getLogger(__name__)

# Search depth of the bitboard `hard` backend. Depth 8 keeps a move well
# under ~50 ms on commodity hardware (see scripts/benchmark_search.py) so the
# GUI stays responsive without a worker thread; the matrix baseline needed
# for comparison remains available via pefforza.agent.minimax.
HARD_BITBOARD_DEPTH = 8

# Time budget of the exact-solver `impossible` backend.
IMPOSSIBLE_TIME_BUDGET = 3.0

# Below this many played tokens a *full* budget is never spent: shallow
# positions almost never fit an interactive weak solve in pure Python, so the
# tier only probes cheaply and falls back fast. The probe is deliberately not
# a bypass: rare shallow positions *are* provable in milliseconds (the PR5
# benchmark documents a 13-ply weak solve at 0.03s), and "proven-optimal
# whenever the proof fits" must stay true for them too. Above the threshold
# the budget itself bounds the response time.
EXACT_SOLVE_MIN_PLIES = 14
OPENING_PROBE_BUDGET = 0.05


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


def exact_agent(
    time_budget: float = IMPOSSIBLE_TIME_BUDGET,
    seed: int | None = None,
    book: OpeningBook | None | Literal["default"] = "default",
) -> Agent:
    """Exact agent - the ``impossible`` backend.

    Opening: the bundled exact opening book (``scripts/build_opening_book.py``)
    answers every position the AI can reach up to its ``max_ply`` with a
    strongly optimal move - fastest win, slowest loss, else a draw.

    Beyond the book the exact solver weak-solves the position under a real
    time budget: the move is proven value-preserving (a won game stays won,
    a drawn one drawn) whenever the solver completes - on the oracle set's
    game lines that is every position, inside the budget
    (``python -m pefforza.agent.evaluate --oracle --difficulty impossible``).
    When a proof does not fit - e.g. an off-book shallow position set up on
    a physical board - the move is a deterministic tactically-safe fallback
    that avoids an immediate loss whenever possible, a one-ply guarantee
    rather than a game-theoretic one.
    Shallow off-book positions (below ``EXACT_SOLVE_MIN_PLIES``) are only
    probed with a small budget. The solver and its transposition table
    persist across the whole game, so later moves reuse earlier proofs.
    Deterministic; ``seed`` is accepted for registry uniformity and ignored.
    """
    solver = PerfectSolver(table_size_bits=21)
    opening = default_book() if book == "default" else book

    def select(board: Board, my_id: int, valid: list[int]) -> int:
        position = BitPosition.from_board(board, to_move=my_id)
        if opening is not None:
            entry = opening.lookup(position)
            if entry is not None and entry.move in valid:
                return entry.move
        budget = time_budget if position.moves >= EXACT_SOLVE_MIN_PLIES else OPENING_PROBE_BUDGET
        move = solver.solve_root(position, time_budget=budget).move
        return move if move in valid else valid[0]

    return tactical_safety_net(select)


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
            "Perfect play: exact opening book, then the exact solver "
            f"(~{IMPOSSIBLE_TIME_BUDGET:.0f}s budget) proves every move; a "
            "tactically-safe fallback only for off-book positions it cannot prove."
        ),
        exact_agent,
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
    "EXACT_SOLVE_MIN_PLIES",
    "HARD_BITBOARD_DEPTH",
    "IMPOSSIBLE_TIME_BUDGET",
    "OPENING_PROBE_BUDGET",
    "bitboard_agent",
    "build_opponent",
    "describe_difficulties",
    "exact_agent",
]
