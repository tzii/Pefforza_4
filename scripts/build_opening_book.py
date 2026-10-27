"""Generate the exact opening book shipped with the ``impossible`` tier.

The book stores, for every position in which the AI is to move up to
``--max-ply`` plies, the move a perfect player makes - *along the lines the
AI itself plays*. The AI's own moves come from the book, so only the
opponent branches: from each AI position the generator plays the book move,
then expands every legal reply. Both colors are covered (AI moving first
and AI moving second).

Moves are strongly optimal (fastest win, slowest loss, draw when neither),
computed by Pascal Pons' native solver - see ``scripts/native_solver.py`` for
how to build it. Ties are broken center-first, the same deterministic order
the Python solver uses. Entries are keyed by
:attr:`pefforza.agent.search.BitPosition.canonical_key`, so mirrored
positions share one entry.

Usage::

    python scripts/build_opening_book.py --solver path/to/c4solver --max-ply 13
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from native_solver import INVALID, NativeSolver  # noqa: E402

from pefforza.agent.search.bitboard import MOVE_ORDER, BitPosition  # noqa: E402
from pefforza.agent.search.book import DEFAULT_BOOK_PATH, OpeningBook  # noqa: E402

_solver: NativeSolver | None = None


def _init_worker(binary: str) -> None:
    global _solver
    _solver = NativeSolver(binary)


def _analyze(moves: tuple[int, ...]) -> tuple[tuple[int, ...], list[int]]:
    assert _solver is not None
    return moves, _solver.analyze(moves)


def best_move(scores: list[int]) -> int:
    top = max(s for s in scores if s != INVALID)
    return next(c for c in MOVE_ORDER if scores[c] == top)


def _add(frontier: dict[int, tuple[int, ...]], pos: BitPosition, moves: tuple[int, ...]) -> None:
    """Queue ``pos`` once, in its canonical orientation.

    Mirrored positions share a book entry, and center-first tie-breaking is
    not mirror-symmetric (it prefers column 2 over 4), so the move must be
    decided in one fixed orientation - the canonical one - for the book to
    be reproducible regardless of worker scheduling.
    """
    key = pos.canonical_key
    if key in frontier:
        return
    if pos.key != key:
        moves = tuple(6 - c for c in moves)
    frontier[key] = moves


def build(binary: str, max_ply: int, workers: int) -> dict[int, tuple[int, int]]:
    """Return ``{canonical_key: (move, score)}`` for both AI colors."""
    entries: dict[int, tuple[int, int]] = {}
    # Frontier of AI-to-move positions, keyed by canonical key -> move list.
    frontier: dict[int, tuple[int, ...]] = {}
    _add(frontier, BitPosition.empty(), ())
    for col in range(7):
        _add(frontier, BitPosition.from_moves([col]), (col,))

    with mp.Pool(workers, initializer=_init_worker, initargs=(binary,)) as pool:
        for ply in range(max_ply + 1):
            level = [m for m in frontier.values() if len(m) == ply]
            if not level:
                continue
            t0 = time.perf_counter()
            results = pool.imap_unordered(_analyze, level, chunksize=64)
            for moves, scores in results:
                pos = BitPosition.from_moves(moves)
                move = best_move(scores)
                key = pos.canonical_key
                assert pos.key == key, "frontier positions are canonical"
                entries[key] = (move, scores[move])

                after = pos.played(move)
                if after.previous_player_won or after.is_full:
                    continue
                for reply in range(7):
                    if not after.can_play(reply):
                        continue
                    child = after.played(reply)
                    if child.previous_player_won or child.is_full:
                        continue
                    if child.moves <= max_ply:
                        _add(frontier, child, (*moves, move, reply))
            print(
                f"ply {ply:2d}: {len(level):7d} positions  ({time.perf_counter() - t0:6.1f}s)",
                flush=True,
            )
    return entries


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--solver", required=True, help="Path to Pons' c4solver binary.")
    p.add_argument("--max-ply", type=int, default=13)
    p.add_argument("--workers", type=int, default=max(1, (mp.cpu_count() or 2) - 1))
    p.add_argument("--out", type=Path, default=DEFAULT_BOOK_PATH)
    args = p.parse_args(argv)

    entries = build(args.solver, args.max_ply, args.workers)
    book = OpeningBook.from_entries(entries, max_ply=args.max_ply)
    book.save(args.out)
    print(f"wrote {len(book)} entries to {args.out} ({args.out.stat().st_size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
