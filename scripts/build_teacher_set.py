"""Generate solver-labelled training positions for the neural tier (offline).

Plays many games in which each side picks the solver's best move with
probability ``--p-best`` and a uniformly random legal move otherwise, so the
positions resemble real play while still covering mistakes. Every
non-terminal position is kept once (mirror images are added at training
time, not here) and labelled with the exact score of all seven columns from
Pascal Pons' native solver (see ``scripts/native_solver.py``).

Output: a ``.npz`` with ``boards`` (N, 6, 7) int8 from the perspective of
the side to move (1 = self, 2 = opponent) and ``scores`` (N, 7) int8, where
``-128`` marks a full column. Feed it to
``python -m pefforza.agent.train --teacher <file>``. The file is large and
fully reproducible from ``--seed``, so it is not committed.

Usage::

    python scripts/build_teacher_set.py --solver path/to/c4solver --games 20000 --out teacher.npz
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from native_solver import INVALID, NativeSolver  # noqa: E402

from pefforza.agent.search.bitboard import MOVE_ORDER, BitPosition  # noqa: E402

FULL_COLUMN = -128

_solver: NativeSolver | None = None


def _init_worker(binary: str) -> None:
    global _solver
    _solver = NativeSolver(binary)


def _play_games(job: tuple[int, int, float]) -> list[tuple[bytes, bytes]]:
    seed, games, p_best = job
    assert _solver is not None
    rng = random.Random(seed)
    out: list[tuple[bytes, bytes]] = []
    for _ in range(games):
        moves: list[int] = []
        pos = BitPosition.empty()
        while not pos.is_full:
            scores = _solver.analyze(moves)
            board = pos.to_board()
            if pos.to_move == 2:  # store from the mover's perspective
                board = np.where(board == 0, 0, 3 - board).astype(np.int8)
            labels = np.array([FULL_COLUMN if s == INVALID else s for s in scores], np.int8)
            out.append((board.tobytes(), labels.tobytes()))
            legal = [c for c in range(7) if scores[c] != INVALID]
            if rng.random() < p_best:
                top = max(scores[c] for c in legal)
                col = next(c for c in MOVE_ORDER if scores[c] == top)
            else:
                col = rng.choice(legal)
            pos = pos.played(col)
            moves.append(col)
            if pos.previous_player_won:
                break
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--solver", required=True, help="Path to Pons' c4solver binary.")
    p.add_argument("--games", type=int, default=20_000)
    p.add_argument("--p-best", type=float, default=0.75)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--workers", type=int, default=max(1, (mp.cpu_count() or 2) - 1))
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)

    per_job = 100
    jobs = [
        (args.seed * 1_000_003 + i, min(per_job, args.games - i * per_job), args.p_best)
        for i in range((args.games + per_job - 1) // per_job)
    ]
    seen: dict[bytes, bytes] = {}
    with mp.Pool(args.workers, initializer=_init_worker, initargs=(args.solver,)) as pool:
        for i, chunk in enumerate(pool.imap(_play_games, jobs), 1):
            for board, labels in chunk:
                seen.setdefault(board, labels)
            if i % 20 == 0 or i == len(jobs):
                print(f"{i * per_job:>7} games, {len(seen):>8} unique positions", flush=True)

    boards = np.frombuffer(b"".join(seen), dtype=np.int8).reshape(-1, 6, 7)
    scores = np.frombuffer(b"".join(seen.values()), dtype=np.int8).reshape(-1, 7)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out, boards=boards, scores=scores)
    print(f"wrote {len(boards)} positions to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
