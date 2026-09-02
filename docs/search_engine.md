# Search engine status

Pefforza currently keeps two search paths side by side.

## Matrix baseline

`pefforza.agent.minimax.MinimaxAgent` is the correctness baseline and the
engine behind the `impossible` tier (time-budgeted iterative deepening). Its
root alpha-beta handling, mate distance scoring, and iterative-deepening
deadline were corrected before any representation rewrite.

Important invariants:

- fail-low alpha-beta values are bounds, not exact root ties;
- mate scores are derived from root-relative `ply`, not `self.depth`;
- time-budgeted search publishes only fully completed iterations;
- `SearchResult.elapsed` is total iterative-search wall time.

## Bitboard path

`pefforza.agent.search` backs the public `hard` tier
(`pefforza.agent.difficulty.bitboard_agent`, depth 8) and hosts the exact
solver prototype.

- `BitPosition` uses seven bits per column: six playable cells and one sentinel;
- `BitboardSearchAgent` keeps the legacy heuristic semantics but uses integer
  bit operations plus a transposition table. The differential tests in
  `tests/test_bitboard_search.py` pin it to the matrix baseline on a seeded
  random corpus (same score, same best move), with and without the TT, and
  under position mirroring;
- `PerfectSolver` removes the static heuristic and searches exact terminal
  scores. Phase 2 is complete: move generation uses the pure bit-mask
  formulas (immediate wins, forced replies to single threats, double-threat
  losses, exclusion of moves that open an opponent win), the transposition
  table is symmetry-canonical and fixed-size (packed parallel int arrays,
  replace-always), and move ordering prefers TT hints and moves that create
  the most winning spots. A 12-ply strong solve runs in well under a second
  (`python scripts/benchmark_search.py`).

## Exact `impossible` tier and the opening decision (PR5)

The public `impossible` tier is now backed by the exact solver through
`PerfectSolver.solve_root`, an *anytime* root search: root moves are
weak-solved in deterministic order (most winning spots first, center-first
on ties) under one real time budget (~3s). Whenever a proof fits the budget
the move is game-theoretically optimal; otherwise the tier plays a
deterministic non-losing fallback (`opening_fallback_move`) that never
gifts an immediate win. Below `EXACT_SOLVE_MIN_PLIES` (14) the budget is
not spent at all: no known shallow position fits an interactive weak solve
in pure Python, so the fallback answers instantly.

The benchmark data behind this design (`--skip-solver` off):

- weak-solve cost is *position-dependent, not monotonic in ply*: a 13-ply
  position solved in 0.03s, a 14-ply one needed 9.5s, a 16-ply one timed
  out at 10s while an 18-ply one took 3 nodes. No ply floor can bound the
  response time - only the time budget can, which is exactly what
  `solve_root` guarantees;
- the empty board answers instantly via the fallback (center column),
  meeting the "interactive from move one" requirement.

Native-backend decision: a C++/pybind11 solver (or the public 8-ply
opening databases) would push proven-optimal play into the deep opening,
but the anytime tier is already interactive and never loses by accident of
budget. The native backend stays deferred until benchmarks show the
fallback losing winnable games - revisit when the RL harness (PR7) can
measure exactly that.

## Reproducible benchmark

Run:

```bash
python scripts/benchmark_search.py --depths 6 8 10
```

On the development review environment, the empty-board comparison was:

| depth | matrix | bitboard + TT | speedup |
|---:|---:|---:|---:|
| 6 | 0.104 s | 0.0064 s | ~16x |
| 8 | 0.751 s | 0.0419 s | ~18x |
| 10 | 6.888 s | 0.242 s | ~28x |

These numbers are machine-dependent. The important result is that both engines
returned the same column and score at each tested depth while the bitboard
engine visited fewer nodes and removed most NumPy/window-scanning overhead.
