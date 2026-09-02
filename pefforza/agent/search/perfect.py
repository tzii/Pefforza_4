"""Exact Connect Four solver backing the public ``impossible`` tier.

Phase 2 of the solver roadmap: threat pruning and move generation use the
pure bit-mask formulas (immediate-win detection, forced replies, double-
threat losses, and exclusion of moves that open an opponent win), the
transposition table is symmetry-canonical and fixed-size, and move ordering
prefers the transposition move and the moves creating the most winning
spots. :meth:`PerfectSolver.solve_root` turns the solver into an anytime
player - proven-optimal moves whenever a proof fits the time budget, with a
deterministic tactically-safe fallback (never gifts an immediate win) when
it does not. An exact opening book / native backend remains the known next
step for proven play from move one; see docs/search_engine.md for the
benchmark decision.
"""

from __future__ import annotations

import time
from array import array
from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal

from pefforza.constants import COLS

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


Outcome = Literal["win_now", "proven_win", "proven_draw", "all_lost", "fallback"]


@dataclass(frozen=True, slots=True)
class RootResult:
    """Result of :meth:`PerfectSolver.solve_root` (anytime interactive play).

    ``outcome`` explains the provenance: ``win_now`` / ``proven_win`` /
    ``proven_draw`` / ``all_lost`` carry a proof (``proven=True``);
    ``fallback`` means the budget expired and the move is only guaranteed
    not to gift an immediate win.
    """

    move: int
    outcome: Outcome
    proven: bool
    nodes: int
    elapsed: float


def opening_fallback_move(position: BitPosition) -> int:
    """Deterministic tactically-safe move for positions without proof time.

    Takes an immediate win if one exists, else a move that does not gift the
    opponent an immediate win (one-ply safety), preferring the ones creating
    the most winning spots (center-first on ties). This is *not* a
    game-theoretic guarantee: it only avoids an immediate loss whenever an
    avoiding move exists. Returns -1 only when no legal move exists.
    """
    wins = position.winning_moves_mask()
    if wins:
        return next(col for col in MOVE_ORDER if wins & COLUMN_MASKS[col])

    safe = position.non_losing_moves_mask()
    candidates = [col for col in MOVE_ORDER if safe & COLUMN_MASKS[col]]
    if not candidates:
        legal = [col for col in MOVE_ORDER if position.can_play(col)]
        return legal[0] if legal else -1

    def spots(col: int) -> int:
        bit = position.move_bit(col)
        return compute_winning_positions(position.current | bit, position.mask | bit).bit_count()

    candidates.sort(key=spots, reverse=True)  # stable: ties keep center-first order
    return candidates[0]


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

    def solve_root(self, position: BitPosition, *, time_budget: float = 3.0) -> RootResult:
        """Anytime exact move choice for interactive play.

        Root moves are weak-solved in deterministic order (most winning spots
        first, center-first on ties, transposition hint first) under one
        shared deadline. Returns a proven winning or drawing move whenever a
        proof fits the budget. On timeout the fallback is the first *not yet
        refuted* move in that order - a root move already proven losing is
        never returned while an unresolved one exists - and the fallback is
        still tactically safe: it never gifts an immediate win. Optimal
        whenever provable, interactive always.
        """
        if time_budget <= 0:
            raise ValueError("time_budget must be > 0")

        start = time.perf_counter()
        wins = position.winning_moves_mask()
        if wins:
            move = next(col for col in MOVE_ORDER if wins & COLUMN_MASKS[col])
            return RootResult(move, "win_now", True, 0, time.perf_counter() - start)

        safe = position.non_losing_moves_mask()
        if safe == 0:
            # Every move loses; still play one, in deterministic order.
            legal = [col for col in MOVE_ORDER if position.can_play(col)]
            move = legal[0] if legal else -1
            return RootResult(move, "all_lost", True, 0, time.perf_counter() - start)

        ordered = self._ordered_columns(position, safe, self._root_hint(position))
        self._nodes = 0
        proven_draw: int | None = None
        proven_losing: set[int] = set()
        timed_out = False
        self._deadline = start + time_budget
        try:
            for col in ordered:
                try:
                    self._check_deadline()
                    value = self._negamax(position.played(col), -1, 1)
                except PerfectSearchTimeoutError:
                    timed_out = True
                    break
                outcome = (value > 0) - (value < 0)
                if outcome < 0:  # opponent, to move in the child, loses
                    return RootResult(
                        col, "proven_win", True, self._nodes, time.perf_counter() - start
                    )
                if outcome == 0:
                    if proven_draw is None:
                        proven_draw = col
                else:
                    # The opponent wins from the child: this root move is
                    # refuted and must never be the timeout fallback.
                    proven_losing.add(col)
        finally:
            self._deadline = None

        elapsed = time.perf_counter() - start
        if not timed_out:
            if proven_draw is not None:
                return RootResult(proven_draw, "proven_draw", True, self._nodes, elapsed)
            return RootResult(ordered[0], "all_lost", True, self._nodes, elapsed)
        if proven_draw is not None:
            # A proven draw beats any unproven move, even on timeout.
            return RootResult(proven_draw, "proven_draw", True, self._nodes, elapsed)
        unresolved = [col for col in ordered if col not in proven_losing]
        move = unresolved[0] if unresolved else ordered[0]
        return RootResult(move, "fallback", False, self._nodes, elapsed)

    def _root_hint(self, position: BitPosition) -> int | None:
        """Best-move hint for root ordering, mirror-corrected.

        The persistent table may hold an entry for this exact position from
        an earlier turn of the same game; reusing its move as the first root
        candidate can be the difference between proving in budget and
        falling back. Symmetry-canonical entries store the move in the
        canonical orientation, so it is mirrored back when this position is
        itself the mirrored variant. Hint only - it can never change scores.
        """
        canonical = position.key == position.canonical_key
        entry = self._table.get(position.canonical_key)
        if entry is None or entry[2] is None:
            return None
        move = entry[2]
        return move if canonical else COLS - 1 - move

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
        canonical = position.key == key
        entry = self._table.get(key)
        tt_move: int | None = None
        if entry is not None:
            value, bound, tt_move = entry
            # Entries store the best move in the canonical orientation; this
            # position may be the mirrored variant, in which case the hint
            # must be mirrored back to stay a useful ordering hint.
            if tt_move is not None and not canonical:
                tt_move = COLS - 1 - tt_move
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
        # Mirror the stored move into the canonical orientation (see _root_hint).
        store_move = best_col if best_col is None or canonical else COLS - 1 - best_col
        self._table.put(key, best, bound, store_move)
        return best


__all__ = [
    "ExactBound",
    "Outcome",
    "PerfectResult",
    "PerfectSearchTimeoutError",
    "PerfectSolver",
    "RootResult",
    "opening_fallback_move",
]
