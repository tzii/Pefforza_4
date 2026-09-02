"""Compare the legacy NumPy minimax with the bitboard engine and exact solver.

Also answers the PR5 "Python vs native backend" question with data: the
opening section times weak solves across ply depths and the anytime
solve_root on the empty board, showing where proofs stop fitting an
interactive budget in pure Python.
"""

from __future__ import annotations

import argparse
import random

from pefforza.agent.minimax import MinimaxAgent
from pefforza.agent.search import (
    BitboardSearchAgent,
    BitPosition,
    PerfectSearchTimeoutError,
    PerfectSolver,
)
from pefforza.rules import empty_board

# Mid-game position (12 plies, no immediate win available): deep enough that
# the solver does real work, shallow enough to finish in seconds.
SOLVER_MOVES = [3, 3, 4, 2, 4, 5, 2, 1, 5, 0, 2, 6]


def _quiet_position(rng: random.Random, plies: int) -> BitPosition:
    """Random non-terminal position with no immediate win or forced loss."""
    while True:
        pos = BitPosition.empty()
        for _ in range(plies):
            legal = pos.legal_columns(center_first=False)
            if not legal:
                break
            pos = pos.played(rng.choice(legal))
            if pos.previous_player_won:
                break
        if (
            not pos.previous_player_won
            and not pos.is_full
            and not pos.winning_moves_mask()
            and pos.non_losing_moves_mask()
        ):
            return pos


def benchmark_opening(budget: float, samples_per_ply: int) -> None:
    print()
    print(f"opening decision data (weak solve, budget {budget:.0f}s per position):")
    rng = random.Random(4242)
    solved_within_budget = 0
    total = 0
    for plies in (12, 14, 16, 18, 20):
        for _ in range(samples_per_ply):
            pos = _quiet_position(rng, plies)
            solver = PerfectSolver(table_size_bits=20)
            try:
                result = solver.solve(pos, weak=True, time_budget=budget)
                print(
                    f"  ply={plies}: score={result.score} nodes={result.nodes} "
                    f"elapsed={result.elapsed:.2f}s"
                )
                solved_within_budget += 1
            except PerfectSearchTimeoutError:
                print(f"  ply={plies}: TIMEOUT >{budget:.0f}s")
            total += 1
    print(f"  solved within budget: {solved_within_budget}/{total}")
    print("  (cost is position-dependent, not monotonic in ply - the tier's")
    print("   guarantee is the time budget, not a ply floor)")

    print()
    print("anytime solve_root on the empty board (worst interactive case):")
    for budget_s in (0.5, 3.0):
        solver = PerfectSolver(table_size_bits=20)
        result = solver.solve_root(BitPosition.empty(), time_budget=budget_s)
        print(
            f"  budget={budget_s}s: move={result.move} outcome={result.outcome} "
            f"nodes={result.nodes} elapsed={result.elapsed:.2f}s"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--depths", nargs="+", type=int, default=[6, 8, 10])
    parser.add_argument("--skip-solver", action="store_true", help="Only benchmark depth engines.")
    parser.add_argument(
        "--skip-opening",
        action="store_true",
        help="Skip the opening decision benchmark (slow).",
    )
    parser.add_argument(
        "--opening-budget",
        type=float,
        default=10.0,
        help="Per-position budget for the opening section.",
    )
    parser.add_argument(
        "--opening-samples", type=int, default=2, help="Positions sampled per ply depth."
    )
    args = parser.parse_args()

    board = empty_board()
    print("depth,engine,column,score,nodes,elapsed_s,tt_hits")
    for depth in args.depths:
        legacy = MinimaxAgent(depth=depth, seed=0).search(board, 1, depth)
        print(
            f"{depth},matrix,{legacy.column},{legacy.score},{legacy.nodes},{legacy.elapsed:.6f},0"
        )

        bit = BitboardSearchAgent(depth=depth, use_tt=True).search(board, 1, depth)
        print(
            f"{depth},bitboard_tt,{bit.column},{bit.score},"
            f"{bit.nodes},{bit.elapsed:.6f},{bit.tt_hits}"
        )

    if args.skip_solver:
        return
    print()
    print(f"exact solver, {len(SOLVER_MOVES)} plies, strong mode:")
    for weak in (True, False):
        result = PerfectSolver().solve(
            BitPosition.from_moves(SOLVER_MOVES), weak=weak, time_budget=300
        )
        mode = "weak" if weak else "strong"
        print(f"  {mode}: score={result.score} nodes={result.nodes} elapsed={result.elapsed:.3f}s")

    if not args.skip_opening:
        benchmark_opening(args.opening_budget, args.opening_samples)


if __name__ == "__main__":
    main()
