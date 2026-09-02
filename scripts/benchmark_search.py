"""Compare the legacy NumPy minimax with the bitboard engine and exact solver."""

from __future__ import annotations

import argparse

from pefforza.agent.minimax import MinimaxAgent
from pefforza.agent.search import BitboardSearchAgent, BitPosition, PerfectSolver
from pefforza.rules import empty_board

# Mid-game position (12 plies, no immediate win available): deep enough that
# the solver does real work, shallow enough to finish in seconds.
SOLVER_MOVES = [3, 3, 4, 2, 4, 5, 2, 1, 5, 0, 2, 6]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--depths", nargs="+", type=int, default=[6, 8, 10])
    parser.add_argument("--skip-solver", action="store_true", help="Only benchmark depth engines.")
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


if __name__ == "__main__":
    main()
