"""Depth-limited alpha-beta search on :mod:`.bitboard` positions.

This is the migration step away from the NumPy search engine. It keeps the
legacy heuristic semantics but adds a transposition table and integer-only
board operations, and backs the public ``hard`` difficulty tier (see
:func:`pefforza.agent.difficulty.bitboard_agent`). The legacy matrix engine
remains the correctness baseline: ``tests/test_bitboard_search.py`` pins the
two engines to identical scores and best moves on a corpus of positions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum, auto

from pefforza.rules import Board

from .bitboard import TOTAL_CELLS, BitPosition, has_alignment
from .heuristic import evaluate_bit_position

MATE_SCORE = 100_000
INF = 1_000_000


def _mate_to_table(value: int, ply: int) -> int:
    if value >= MATE_SCORE - TOTAL_CELLS:
        return value + ply
    if value <= -MATE_SCORE + TOTAL_CELLS:
        return value - ply
    return value


def _mate_from_table(value: int, ply: int) -> int:
    return _mate_to_table(value, -ply)


class Bound(Enum):
    EXACT = auto()
    LOWER = auto()
    UPPER = auto()


@dataclass(slots=True)
class TTEntry:
    depth: int
    value: int
    bound: Bound
    best_move: int | None


@dataclass(frozen=True, slots=True)
class BitSearchResult:
    column: int
    score: int
    depth: int
    nodes: int
    elapsed: float
    tt_hits: int


class BitboardSearchAgent:
    """Deterministic depth-limited negamax with alpha-beta and a TT."""

    def __init__(self, depth: int = 8, *, use_tt: bool = True) -> None:
        if depth < 1:
            raise ValueError("depth must be >= 1")
        self.depth = depth
        self.use_tt = use_tt
        self._table: dict[int, TTEntry] = {}
        self._nodes = 0
        self._tt_hits = 0

    def clear_cache(self) -> None:
        self._table.clear()

    def select(self, board: Board, my_id: int, valid: list[int]) -> int:
        result = self.search(board, my_id)
        return result.column if result.column in valid else valid[0]

    def search(self, board: Board, my_id: int, depth: int | None = None) -> BitSearchResult:
        depth = self.depth if depth is None else depth
        if depth < 1:
            raise ValueError("depth must be >= 1")

        position = BitPosition.from_board(board, to_move=my_id)
        self._nodes = 0
        self._tt_hits = 0
        start = time.perf_counter()
        col, score = self._root(position, depth)
        return BitSearchResult(
            column=col,
            score=score,
            depth=depth,
            nodes=self._nodes,
            elapsed=time.perf_counter() - start,
            tt_hits=self._tt_hits,
        )

    def analyze(self, board: Board, my_id: int, depth: int | None = None) -> dict[int, int]:
        """Return exact full-window depth-limited scores for all legal moves."""
        depth = self.depth if depth is None else depth
        if depth < 1:
            raise ValueError("depth must be >= 1")
        position = BitPosition.from_board(board, to_move=my_id)
        scores: dict[int, int] = {}
        self._nodes = 0
        self._tt_hits = 0
        if position.previous_player_won or has_alignment(position.current):
            return scores
        for col in position.legal_columns():
            child = position.played(col)
            scores[col] = -self._negamax(child, depth - 1, -INF, INF, ply=1)
        return scores

    def _ordered_columns(self, position: BitPosition, tt_move: int | None) -> list[int]:
        legal = position.legal_columns()
        if tt_move is not None and tt_move in legal:
            legal.remove(tt_move)
            legal.insert(0, tt_move)
        return legal

    def _root(self, position: BitPosition, depth: int) -> tuple[int, int]:
        if position.previous_player_won:
            return -1, -MATE_SCORE
        if has_alignment(position.current):
            return -1, MATE_SCORE
        legal = position.legal_columns()
        if not legal:
            return -1, 0

        alpha = -INF
        beta = INF
        best_col = legal[0]

        # Root ordering is deliberately TT-independent. A best_move left in
        # the table by an earlier search of a transposed position would make
        # the published move depend on the engine's search history even when
        # the candidates score identically; center-first keeps the root
        # deterministic across agent reuse (same principle as matrix patch 4.1).
        for col in self._ordered_columns(position, None):
            child = position.played(col)
            score = -self._negamax(child, depth - 1, -beta, -alpha, ply=1)
            # As in the corrected matrix engine, fail-low values are bounds and
            # must not be treated as exact ties at the root.
            if score > alpha:
                alpha = score
                best_col = col

        if self.use_tt:
            self._table[position.key] = TTEntry(depth, alpha, Bound.EXACT, best_col)
        return best_col, alpha

    def _negamax(
        self,
        position: BitPosition,
        depth: int,
        alpha: int,
        beta: int,
        *,
        ply: int,
    ) -> int:
        self._nodes += 1

        if position.previous_player_won:
            return -MATE_SCORE + ply
        if position.is_full:
            return 0
        if depth == 0:
            return evaluate_bit_position(position)

        alpha_in = alpha
        beta_in = beta
        tt_move: int | None = None

        if self.use_tt:
            entry = self._table.get(position.key)
            # A deeper heuristic horizon is not the requested fixed-depth value.
            if entry is not None and entry.depth == depth:
                self._tt_hits += 1
                tt_move = entry.best_move
                value = _mate_from_table(entry.value, ply)
                if entry.bound is Bound.EXACT:
                    return value
                if entry.bound is Bound.LOWER:
                    alpha = max(alpha, value)
                else:
                    beta = min(beta, value)
                if alpha >= beta:
                    return value
            elif entry is not None:
                tt_move = entry.best_move

        best = -INF
        best_col: int | None = None
        for col in self._ordered_columns(position, tt_move):
            child = position.played(col)
            score = -self._negamax(child, depth - 1, -beta, -alpha, ply=ply + 1)
            if score > best:
                best = score
                best_col = col
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break

        if self.use_tt:
            if best <= alpha_in:
                bound = Bound.UPPER
            elif best >= beta_in:
                bound = Bound.LOWER
            else:
                bound = Bound.EXACT
            # Store mate distance from this position, not from a previous root.
            self._table[position.key] = TTEntry(depth, _mate_to_table(best, ply), bound, best_col)

        return best


__all__ = [
    "BitSearchResult",
    "BitboardSearchAgent",
    "Bound",
    "INF",
    "MATE_SCORE",
    "TTEntry",
]
