"""Exact Connect Four solver foundation.

Phase 2 of the solver roadmap: threat pruning and move generation use the
pure bit-mask formulas (immediate-win detection, forced replies, double-
threat losses, and exclusion of moves that open an opponent win), the
transposition table is symmetry-canonical and fixed-size, and move ordering
prefers the transposition move and the moves creating the most winning
spots. It is deliberately not connected to the public ``impossible`` tier
yet: solving the hardest opening positions interactively still needs an
opening book and/or a native backend.
"""

from __future__ import annotations

import time
from array import array
from dataclasses import dataclass
from enum import Enum, auto

from .bitboard import (
    COLUMN_MASKS,
    MOVE_ORDER,
    TOTAL_CELLS,
    BitPosition,
    compute_winning_positions,
)


class PerfectSearchTimeoutError(RuntimeError):
    pass


class ExactBound(Enum):
    EXACT = auto()
    LOWER = auto()
    UPPER = auto()


_BOUND_TO_CODE = {ExactBound.EXACT: 0, ExactBound.LOWER: 1, ExactBound.UPPER: 2}
_BOUND_FROM_CODE = (ExactBound.EXACT, ExactBound.LOWER, ExactBound.UPPER)
_NO_MOVE_CODE = 0b111


class _TranspositionTable:
    """Fixed-size, replace-always transposition table over parallel int arrays.

    A plain dict grows without bound and pays hashing/object overhead; this
    table indexes ``key % size`` directly into two ``array('q')`` buffers and
    stores each entry packed into one int: 6 bits of score, 2 bits of bound,
    3 bits of best move. Collisions replace the previous entry - standard for
    game solvers, deterministic for a given size, and no correctness impact
    because stored values are always sound alpha-beta bounds.
    """

    __slots__ = ("_keys", "_entries", "_index_mask")

    def __init__(self, size_bits: int) -> None:
        if not 4 <= size_bits <= 30:
            raise ValueError("size_bits must be in [4, 30]")
        size = 1 << size_bits
        self._index_mask = size - 1
        # -1 in every key slot marks "empty"; entries start packed as zeroes.
        self._keys = array("q", b"\xff" * (8 * size))
        self._entries = array("q", bytes(8 * size))

    def get(self, key: int) -> tuple[int, ExactBound, int | None] | None:
        index = key & self._index_mask
        if self._keys[index] != key:
            return None
        packed = self._entries[index]
        move = packed & 0b111
        return (
            ((packed >> 5) & 0b111111) - 32,
            _BOUND_FROM_CODE[(packed >> 3) & 0b11],
            None if move == _NO_MOVE_CODE else move,
        )

    def put(self, key: int, value: int, bound: ExactBound, best_move: int | None) -> None:
        index = key & self._index_mask
        self._keys[index] = key
        move = _NO_MOVE_CODE if best_move is None else best_move
        self._entries[index] = ((value + 32) << 5) | (_BOUND_TO_CODE[bound] << 3) | move

    def clear(self) -> None:
        self._keys = array("q", b"\xff" * len(self._keys) * 8)
        self._entries = array("q", bytes(len(self._entries) * 8))


@dataclass(frozen=True, slots=True)
class PerfectResult:
    score: int
    nodes: int
    elapsed: float


class PerfectSolver:
    """Exact win/draw/loss solver for legal non-terminal positions."""

    def __init__(self, table_size_bits: int = 20) -> None:
        self._table = _TranspositionTable(table_size_bits)
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

        def winning_spots(col: int) -> int:
            bit = position.move_bit(col)
            after = compute_winning_positions(position.current | bit, position.mask | bit)
            return after.bit_count()

        # Stable sort: equal winning-spot counts keep the center-first order.
        cols.sort(key=winning_spots, reverse=True)
        # Note: with a symmetry-canonical TT the stored best move may come
        # from the mirrored variant; it is only an ordering hint, so using it
        # unchanged can never change scores.
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

        key = position.canonical_key
        entry = self._table.get(key)
        tt_move: int | None = None
        if entry is not None:
            value, bound, tt_move = entry
            if bound is ExactBound.EXACT:
                return value
            if bound is ExactBound.LOWER:
                alpha = max(alpha, value)
            else:
                beta = min(beta, value)
            if alpha >= beta:
                return value

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
        self._table.put(key, best, bound, best_col)
        return best


__all__ = [
    "ExactBound",
    "PerfectResult",
    "PerfectSearchTimeoutError",
    "PerfectSolver",
]
