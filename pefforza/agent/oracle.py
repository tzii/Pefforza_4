"""Exact-oracle evaluation: how often does an agent play a perfect move?

Win rates against fixed opponents say little about a near-perfect player -
it beats everything in the zoo. The oracle set instead holds positions with
the exact score of *every* legal move (computed offline by a native solver,
see ``scripts/build_oracle_set.py``), so each agent decision can be graded:

* **value-preserving** - the move keeps the game-theoretic outcome (a won
  position stays won, a drawn one stays drawn). This is the weak-solving
  notion of perfect play;
* **exactly optimal** - the move also has the best exact score: the fastest
  win, or the slowest loss.

Scores use the solver convention from the side to move: 0 draw, ``s > 0``
win with ``s`` of the mover's stones left in hand, ``s < 0`` loss.

The set mixes two populations: ``line`` positions arise in games where the
side being evaluated plays perfectly and the opponent half-perfectly, half
randomly (what a strong agent actually faces); ``random`` positions come
from two noisy players, covering stranger, off-book territory.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from pefforza.agent.evaluate import Agent
from pefforza.constants import COLS, ROWS
from pefforza.rules import Board, available_columns

DEFAULT_ORACLE_PATH = Path(__file__).resolve().parent / "data" / "oracle_positions.json"

# Ply buckets used in reports: opening, early middlegame, middlegame, endgame.
DEFAULT_BUCKETS: tuple[tuple[int, int], ...] = ((0, 11), (12, 17), (18, 25), (26, 41))


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


@dataclass(frozen=True)
class OraclePosition:
    moves: tuple[int, ...]
    scores: tuple[int | None, ...]  # None for full columns
    source: str = "line"

    @property
    def ply(self) -> int:
        return len(self.moves)

    @property
    def to_move(self) -> int:
        return 1 if self.ply % 2 == 0 else 2

    @property
    def best_score(self) -> int:
        return max(s for s in self.scores if s is not None)

    def board(self) -> Board:
        board = np.zeros((ROWS, COLS), dtype=np.int8)
        heights = [ROWS - 1] * COLS
        for i, col in enumerate(self.moves):
            board[heights[col], col] = 1 if i % 2 == 0 else 2
            heights[col] -= 1
        return board

    def is_optimal(self, move: int) -> bool:
        score = self.scores[move]
        return score is not None and score == self.best_score

    def preserves_value(self, move: int) -> bool:
        score = self.scores[move]
        return score is not None and _sign(score) == _sign(self.best_score)


def load_oracle_positions(path: Path | str = DEFAULT_ORACLE_PATH) -> list[OraclePosition]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        OraclePosition(
            moves=tuple(int(c) - 1 for c in item["moves"]),
            scores=tuple(item["scores"]),
            source=item.get("source", "line"),
        )
        for item in data["positions"]
    ]


@dataclass
class BucketStats:
    positions: int = 0
    value_preserving: int = 0
    optimal: int = 0
    max_seconds: float = 0.0

    def add(self, preserving: bool, optimal: bool, seconds: float) -> None:
        self.positions += 1
        self.value_preserving += preserving
        self.optimal += optimal
        self.max_seconds = max(self.max_seconds, seconds)

    @property
    def value_rate(self) -> float:
        return self.value_preserving / self.positions if self.positions else 0.0

    @property
    def optimal_rate(self) -> float:
        return self.optimal / self.positions if self.positions else 0.0


@dataclass
class OracleReport:
    buckets: dict[tuple[int, int], BucketStats]
    total: BucketStats = field(default_factory=BucketStats)
    mistakes: list[tuple[OraclePosition, int]] = field(default_factory=list)

    def __str__(self) -> str:
        lines = ["plies    positions  value-preserving  exactly-optimal  slowest move"]
        rows = [*self.buckets.items(), (("all", ""), self.total)]
        for (lo, hi), stats in rows:
            label = f"{lo}-{hi}" if hi != "" else str(lo)
            if not stats.positions:
                continue
            lines.append(
                f"{label:<8} {stats.positions:>9}  {stats.value_rate:>15.1%}  "
                f"{stats.optimal_rate:>15.1%}  {stats.max_seconds:>10.2f}s"
            )
        return "\n".join(lines)


def oracle_evaluate(
    agent: Agent,
    positions: Iterable[OraclePosition],
    buckets: Sequence[tuple[int, int]] = DEFAULT_BUCKETS,
) -> OracleReport:
    """Grade ``agent``'s move in every position against the exact scores."""
    report = OracleReport({b: BucketStats() for b in buckets})
    for pos in positions:
        board = pos.board()
        valid = available_columns(board)
        start = time.perf_counter()
        move = int(agent(board, pos.to_move, valid))
        elapsed = time.perf_counter() - start
        preserving = pos.preserves_value(move)
        optimal = pos.is_optimal(move)
        report.total.add(preserving, optimal, elapsed)
        for lo, hi in buckets:
            if lo <= pos.ply <= hi:
                report.buckets[(lo, hi)].add(preserving, optimal, elapsed)
                break
        if not preserving:
            report.mistakes.append((pos, move))
    return report


__all__ = [
    "DEFAULT_BUCKETS",
    "DEFAULT_ORACLE_PATH",
    "BucketStats",
    "OraclePosition",
    "OracleReport",
    "load_oracle_positions",
    "oracle_evaluate",
]
