"""Exact Connect Four solver foundation.

The solver is functional for late/mid-game positions and uses exact terminal
scores, alpha-beta bounds, a transposition table, and direct-loss pruning. It
is deliberately not connected to the public ``impossible`` tier yet: solving
the hardest opening positions interactively still needs stronger move ordering
and/or an opening book (and may later warrant a native backend).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum, auto

from .bitboard import COLUMN_MASKS, MOVE_ORDER, TOTAL_CELLS, BitPosition


class PerfectSearchTimeoutError(RuntimeError):
    pass


class ExactBound(Enum):
    EXACT = auto()
    LOWER = auto()
    UPPER = auto()


@dataclass(slots=True)
class ExactEntry:
    value: int
    bound: ExactBound
    best_move: int | None


@dataclass(frozen=True, slots=True)
class PerfectResult:
    score: int
    nodes: int
    elapsed: float


class PerfectSolver:
    """Exact win/draw/loss solver for legal non-terminal positions."""

    def __init__(self) -> None:
        self._table: dict[int, ExactEntry] = {}
        self._nodes = 0
        self._deadline: float | None = None

    def clear_cache(self) -> None:
        self._table.clear()

    def solve(
        self,
        position: BitPosition,
        *,
        weak: bool = False,
        time_budget: float | None = None,
    ) -> PerfectResult:
        """Return the exact game-theoretic score.

        Positive means the player to move can force a win, zero a draw, and
        negative a forced loss. Magnitude encodes distance to the game end,
        following the conventional Connect Four solver score.

        ``weak=True`` computes only win/draw/loss (-1/0/+1), which is often
        sufficient for an "impossible" opponent and permits tighter windows.
        """
        if position.previous_player_won:
            raise ValueError("position is already terminal: previous player won")
        if time_budget is not None and time_budget <= 0:
            raise ValueError("time_budget must be > 0")

        self._nodes = 0
        self._deadline = None if time_budget is None else time.perf_counter() + time_budget
        start = time.perf_counter()
        try:
            score = self._solve_score(position, weak=weak)
        finally:
            self._deadline = None

        return PerfectResult(score=score, nodes=self._nodes, elapsed=time.perf_counter() - start)

    def analyze(
        self,
        position: BitPosition,
        *,
        weak: bool = False,
        time_budget: float | None = None,
    ) -> dict[int, int]:
        """Return exact scores for every legal root move.

        The optional budget applies to the whole analysis. A timeout raises
        :class:`PerfectSearchTimeoutError`; partial scores are deliberately not
        returned as if the analysis were complete.
        """
        if position.previous_player_won:
            raise ValueError("position is already terminal: previous player won")
        if time_budget is not None and time_budget <= 0:
            raise ValueError("time_budget must be > 0")

        self._nodes = 0
        self._deadline = None if time_budget is None else time.perf_counter() + time_budget
        scores: dict[int, int] = {}
        try:
            winning = position.winning_moves_mask()
            for col in position.legal_columns():
                self._check_deadline()
                if winning & COLUMN_MASKS[col]:
                    score = (TOTAL_CELLS + 1 - position.moves) // 2
                    scores[col] = 1 if weak else score
                else:
                    scores[col] = -self._solve_score(position.played(col), weak=weak)
        finally:
            self._deadline = None
        return scores

    def best_move(
        self,
        position: BitPosition,
        *,
        weak: bool = True,
        time_budget: float | None = None,
    ) -> int:
        scores = self.analyze(position, weak=weak, time_budget=time_budget)
        if not scores:
            return -1
        best = max(scores.values())
        return next(col for col in MOVE_ORDER if scores.get(col) == best)

    def _solve_score(self, position: BitPosition, *, weak: bool) -> int:
        self._check_deadline()
        if position.winning_moves_mask():
            score = (TOTAL_CELLS + 1 - position.moves) // 2
            return 1 if weak else score

        if weak:
            # A single narrow search is enough when only the sign matters.
            # Fail-soft may return a magnitude outside [-1, 1], so normalize it
            # explicitly instead of exposing a strong-solver distance score.
            value = self._negamax(position, -1, 1)
            return (value > 0) - (value < 0)

        low = -((TOTAL_CELLS - position.moves) // 2)
        high = (TOTAL_CELLS + 1 - position.moves) // 2

        # Null-window iterative narrowing: each search answers whether the true
        # score lies above or below a candidate threshold.
        while low < high:
            med = low + (high - low) // 2
            if med <= 0 and low // 2 < med:
                med = low // 2
            elif med >= 0 and high // 2 > med:
                med = high // 2
            value = self._negamax(position, med, med + 1)
            if value <= med:
                high = value
            else:
                low = value
        return low

    def _check_deadline(self) -> None:
        if self._deadline is not None and time.perf_counter() >= self._deadline:
            raise PerfectSearchTimeoutError("exact search deadline expired")

    def _ordered_columns(
        self,
        position: BitPosition,
        moves_mask: int,
        tt_move: int | None,
    ) -> list[int]:
        cols = [c for c in MOVE_ORDER if moves_mask & COLUMN_MASKS[c]]
        if tt_move is not None and tt_move in cols:
            cols.remove(tt_move)
            cols.insert(0, tt_move)
        return cols

    def _negamax(self, position: BitPosition, alpha: int, beta: int) -> int:
        self._nodes += 1
        # A per-node check is acceptable in this pure-Python first version and
        # makes the public time budget a real deadline.
        self._check_deadline()

        if position.winning_moves_mask():
            return (TOTAL_CELLS + 1 - position.moves) // 2

        possible = position.non_losing_moves_mask()
        if possible == 0:
            return -((TOTAL_CELLS - position.moves) // 2)

        if position.moves >= TOTAL_CELLS - 2:
            return 0

        alpha_in = alpha
        beta_in = beta

        # Tight mathematical bounds once neither side can win on the next ply.
        min_score = -((TOTAL_CELLS - 2 - position.moves) // 2)
        if alpha < min_score:
            alpha = min_score
            if alpha >= beta:
                return alpha

        max_score = (TOTAL_CELLS - 1 - position.moves) // 2
        if beta > max_score:
            beta = max_score
            if alpha >= beta:
                return beta

        entry = self._table.get(position.key)
        tt_move: int | None = None
        if entry is not None:
            tt_move = entry.best_move
            if entry.bound is ExactBound.EXACT:
                return entry.value
            if entry.bound is ExactBound.LOWER:
                alpha = max(alpha, entry.value)
            else:
                beta = min(beta, entry.value)
            if alpha >= beta:
                return entry.value

        best = -100
        best_col: int | None = None
        for col in self._ordered_columns(position, possible, tt_move):
            score = -self._negamax(position.played(col), -beta, -alpha)
            if score > best:
                best = score
                best_col = col
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break

        if best <= alpha_in:
            bound = ExactBound.UPPER
        elif best >= beta_in:
            bound = ExactBound.LOWER
        else:
            bound = ExactBound.EXACT
        self._table[position.key] = ExactEntry(best, bound, best_col)
        return best


__all__ = [
    "ExactBound",
    "PerfectResult",
    "PerfectSearchTimeoutError",
    "PerfectSolver",
]
