"""Negamax + alpha-beta Connect 4 engine.

Connect 4 has a small branching factor (<=7), so classical search with
alpha-beta pruning and good move ordering plays strongly at modest depths.
This engine backs the time-budgeted "impossible" tier and serves as the
differential-test baseline for the bitboard engine that powers "hard" while
an exact bitboard solver is developed separately.

Implementation notes:
* Boards are mutated in place during search and undone on backtrack to avoid
  per-node copy overhead.
* Move ordering is center-first ([3, 2, 4, 1, 5, 0, 6] for a 7-column board)
  which dramatically improves alpha-beta cutoffs.
* Iterative deepening (``MinimaxAgent.search_with_time_budget``) lets us
  return the deepest *completed* move within a wall-clock deadline - used by
  the "impossible" tier so an unfinished iteration is never published.
* :func:`tactical_safety_net` wraps any agent and forces it to take an
  immediate win or block an immediate threat. This is defense-in-depth: the
  search should already do this, but a 1-ply guard guarantees it.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass

from pefforza.constants import COLS, ROWS, WIN_LENGTH
from pefforza.rules import (
    Board,
    available_columns,
    check_winner,
    is_board_full,
    next_open_row,
)

logger = logging.getLogger(__name__)

# Mate scores must stay well outside the static-evaluation range. ``_INF`` is
# deliberately larger still so alpha/beta bounds can never collide with a
# legal score. Mate distance is encoded with ``ply`` during search: faster wins
# receive a larger positive score and slower losses a less-negative score.
_MATE_SCORE = 100_000
_INF = 1_000_000

# Center-first move ordering for a 7-column board.
_MOVE_ORDER: tuple[int, ...] = tuple(sorted(range(COLS), key=lambda c: abs(c - COLS // 2)))


def _ordered_valid(board: Board) -> list[int]:
    return [c for c in _MOVE_ORDER if board[0, c] == 0]


# --------------------------------------------------------------- evaluation
def _score_window(window: list[int], player: int) -> int:
    """Heuristic score for one length-4 window from ``player``'s perspective."""
    opp = 3 - player
    p = sum(1 for v in window if v == player)
    o = sum(1 for v in window if v == opp)
    e = sum(1 for v in window if v == 0)

    if p == 4:
        return 100
    if p == 3 and e == 1:
        return 5
    if p == 2 and e == 2:
        return 2
    if o == 3 and e == 1:
        # Opponent threat penalty. Immediate threats are handled tactically by
        # the search/safety net; this is only a static horizon heuristic.
        return -4
    return 0


def evaluate_position(board: Board, player: int) -> int:
    """Static evaluation of ``board`` from ``player``'s perspective.

    Not called when the position is terminal (caller checks first).
    """
    score = 0

    # Center-column control bonus.
    center = COLS // 2
    score += int(sum(3 for r in range(ROWS) if board[r, center] == player))

    # Horizontal windows.
    for r in range(ROWS):
        for c in range(COLS - WIN_LENGTH + 1):
            score += _score_window([int(board[r, c + i]) for i in range(WIN_LENGTH)], player)

    # Vertical windows.
    for c in range(COLS):
        for r in range(ROWS - WIN_LENGTH + 1):
            score += _score_window([int(board[r + i, c]) for i in range(WIN_LENGTH)], player)

    # Diagonal "\".
    for r in range(ROWS - WIN_LENGTH + 1):
        for c in range(COLS - WIN_LENGTH + 1):
            score += _score_window([int(board[r + i, c + i]) for i in range(WIN_LENGTH)], player)

    # Diagonal "/".
    for r in range(WIN_LENGTH - 1, ROWS):
        for c in range(COLS - WIN_LENGTH + 1):
            score += _score_window([int(board[r - i, c + i]) for i in range(WIN_LENGTH)], player)

    return score


# --------------------------------------------------------------- search
@dataclass
class SearchResult:
    column: int
    score: int
    depth: int
    nodes: int
    elapsed: float


class _SearchTimeoutError(RuntimeError):
    """Internal control-flow exception for an expired search deadline."""


class MinimaxAgent:
    """Negamax + alpha-beta search agent."""

    def __init__(self, depth: int = 6, seed: int | None = None) -> None:
        if depth < 1:
            raise ValueError("depth must be >= 1")
        self.depth = depth
        # Retained for API/backward compatibility. Root selection is now
        # deterministic because alpha-beta fail-low bounds must not be treated
        # as exact ties (see ``_root``).
        self._rng = random.Random(seed)
        self._nodes = 0
        self._deadline: float | None = None

    # --------------------------------------------------------------- API
    def select(self, board: Board, my_id: int, valid: list[int]) -> int:
        """Return the best column at the configured fixed depth."""
        result = self.search(board, my_id, depth=self.depth)
        if result.column not in valid:
            return valid[0]
        return result.column

    def search(self, board: Board, my_id: int, depth: int) -> SearchResult:
        """Search one fixed depth with no time limit."""
        return self._search_at_depth(board, my_id, depth=depth, deadline=None)

    def search_with_time_budget(
        self,
        board: Board,
        my_id: int,
        time_budget: float = 1.5,
        max_depth: int = 12,
        min_depth: int = 4,
    ) -> SearchResult:
        """Iterative deepening under a real wall-clock deadline.

        Only fully completed iterations are published. If the deadline expires
        mid-iteration, that partial result is discarded and the deepest
        completed result is returned. For extremely small budgets where even
        ``min_depth`` cannot complete, a deterministic legal center-first move
        is returned at depth 0 rather than overrunning the budget by design.

        ``SearchResult.elapsed`` and ``nodes`` describe the *entire* iterative
        search, not only the last completed iteration.
        """
        if time_budget <= 0:
            raise ValueError("time_budget must be > 0")
        if min_depth < 1:
            raise ValueError("min_depth must be >= 1")
        if max_depth < min_depth:
            raise ValueError("max_depth must be >= min_depth")

        start = time.perf_counter()
        deadline = start + time_budget
        valid = _ordered_valid(board)
        if not valid:
            return SearchResult(-1, 0, 0, 0, time.perf_counter() - start)

        # Safe fallback if the caller supplied a budget too small to finish
        # even the first requested iteration.
        best = SearchResult(
            column=valid[0],
            score=evaluate_position(board, my_id),
            depth=0,
            nodes=0,
            elapsed=0.0,
        )
        total_nodes = 0

        for depth in range(min_depth, max_depth + 1):
            if time.perf_counter() >= deadline:
                break
            try:
                candidate = self._search_at_depth(
                    board,
                    my_id,
                    depth=depth,
                    deadline=deadline,
                )
            except _SearchTimeoutError:
                break
            total_nodes += candidate.nodes
            best = candidate

        total_elapsed = time.perf_counter() - start
        return SearchResult(
            column=best.column,
            score=best.score,
            depth=best.depth,
            nodes=total_nodes,
            elapsed=total_elapsed,
        )

    def _search_at_depth(
        self,
        board: Board,
        my_id: int,
        depth: int,
        deadline: float | None,
    ) -> SearchResult:
        if depth < 1:
            raise ValueError("depth must be >= 1")
        self._nodes = 0
        self._deadline = deadline
        start = time.perf_counter()
        try:
            col, score = self._root(board.copy(), my_id, depth)
        finally:
            # Never leak a deadline into a later fixed-depth search.
            self._deadline = None
        elapsed = time.perf_counter() - start
        return SearchResult(col, score, depth, self._nodes, elapsed)

    def _check_deadline(self) -> None:
        if self._deadline is not None and time.perf_counter() >= self._deadline:
            raise _SearchTimeoutError

    # ---------------------------------------------------------- internals
    def _root(self, board: Board, player: int, depth: int) -> tuple[int, int]:
        """Return the best root move and its exact/current alpha score.

        Important correctness detail: values returned by a child searched with
        a narrowed alpha-beta window may be *bounds*, not exact scores. The old
        implementation appended ``score == best_score`` moves to a random tie
        list, which confused fail-low bounds with exact ties and could choose a
        move known to be worse than the current principal variation. We only
        replace the root move when a child strictly improves alpha.
        """
        valid = _ordered_valid(board)
        if not valid:
            return -1, 0

        alpha, beta = -_INF, _INF
        best_col = valid[0]

        for col in valid:
            self._check_deadline()
            row = next_open_row(board, col)
            board[row, col] = player
            try:
                score = -self._negamax(
                    board,
                    depth - 1,
                    -beta,
                    -alpha,
                    3 - player,
                    ply=1,
                )
            finally:
                board[row, col] = 0

            if score > alpha:
                alpha = score
                best_col = col

        return best_col, alpha

    def _negamax(
        self,
        board: Board,
        depth: int,
        alpha: int,
        beta: int,
        player: int,
        *,
        ply: int,
    ) -> int:
        self._nodes += 1
        self._check_deadline()

        winner = check_winner(board)
        if winner != 0:
            # On a legal position the winner is normally the player who just
            # moved (the opponent of ``player``). Keeping the symmetric branch
            # also makes the function robust when called on externally built
            # positions. Mate distance is relative to this root search, never
            # to ``self.depth``.
            if winner == player:
                return _MATE_SCORE - ply
            return -_MATE_SCORE + ply
        if is_board_full(board):
            return 0
        if depth == 0:
            return evaluate_position(board, player)

        best = -_INF
        for col in _ordered_valid(board):
            row = next_open_row(board, col)
            board[row, col] = player
            try:
                score = -self._negamax(
                    board,
                    depth - 1,
                    -beta,
                    -alpha,
                    3 - player,
                    ply=ply + 1,
                )
            finally:
                board[row, col] = 0

            if score > best:
                best = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
        return best


# --------------------------------------------------------- agent factory
def find_immediate_win(board: Board, player: int, valid: list[int]) -> int | None:
    """Return a column that wins for ``player`` on this turn, or None."""
    for c in valid:
        row = next_open_row(board, c)
        if row < 0:
            continue
        board[row, c] = player
        is_win = check_winner(board) == player
        board[row, c] = 0
        if is_win:
            return c
    return None


def tactical_safety_net(agent):
    """Wrap an agent so it always takes immediate wins / blocks immediate threats.

    This is defense-in-depth. A correct minimax should already see 1-ply
    threats, but an explicit 1-ply guard guarantees the AI never lets a
    visible 3-in-a-row complete - even with buggy / weak underlying agents.
    """

    def select(board: Board, my_id: int, valid: list[int]) -> int:
        win = find_immediate_win(board, my_id, valid)
        if win is not None:
            return win
        block = find_immediate_win(board, 3 - my_id, valid)
        if block is not None:
            return block
        return agent(board, my_id, valid)

    return select


def minimax_agent(depth: int = 6, seed: int | None = None):
    """Return a callable Agent (Board, my_id, valid) -> column.

    The returned agent is wrapped with :func:`tactical_safety_net` so it
    always takes immediate wins and blocks immediate threats.
    """
    engine = MinimaxAgent(depth=depth, seed=seed)
    return tactical_safety_net(engine.select)


def impossible_agent(time_budget: float = 3.0, seed: int | None = None):
    """Time-budgeted iterative-deepening minimax - the strongest tier.

    Wrapped with :func:`tactical_safety_net`.
    """
    engine = MinimaxAgent(depth=4, seed=seed)

    def select(board: Board, my_id: int, valid: list[int]) -> int:
        result = engine.search_with_time_budget(
            board,
            my_id,
            time_budget=time_budget,
            min_depth=5,
            max_depth=10,
        )
        if result.column in valid:
            return result.column
        return valid[0]

    return tactical_safety_net(select)


# Re-export the available_columns helper so callers that already import this
# module get a one-stop shop.
__all__ = [
    "MinimaxAgent",
    "SearchResult",
    "available_columns",
    "evaluate_position",
    "find_immediate_win",
    "impossible_agent",
    "minimax_agent",
    "tactical_safety_net",
]
