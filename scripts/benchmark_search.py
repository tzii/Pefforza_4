"""Compare the legacy NumPy minimax with the in-progress bitboard engine."""

from __future__ import annotations

import argparse

from pefforza.agent.minimax import MinimaxAgent
from pefforza.agent.search import BitboardSearchAgent
from pefforza.rules import empty_board


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--depths", nargs="+", type=int, default=[6, 8, 10])
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


if __name__ == "__main__":
    main()
