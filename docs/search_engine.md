# Search engine status

Pefforza currently keeps two search paths side by side.

## Matrix baseline

`pefforza.agent.minimax.MinimaxAgent` is the matrix correctness baseline, not
the current `impossible` backend. It supports time-budgeted iterative deepening. Its
root alpha-beta handling, mate distance scoring, and iterative-deepening
deadline were corrected before any representation rewrite.

Important invariants:

- fail-low alpha-beta values are bounds, not exact root ties;
- mate scores are derived from root-relative `ply`, not `self.depth`;
- time-budgeted search publishes only fully completed iterations;
- `SearchResult.elapsed` is total iterative-search wall time.
- Persistent bitboard entries normalize mate distances to their own position;
  fixed-depth heuristic values are reused only at the matching search depth.

## Bitboard path

`pefforza.agent.search` backs the public `hard` tier
(`pefforza.agent.difficulty.bitboard_agent`, depth 8) and the exact
`impossible` solver.

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
on ties, transposition hint first) under one real time budget (~3s).
Whenever a proof fits the budget the move is game-theoretically optimal.
On timeout the fallback is the first *not yet refuted* root move - a move
already proven losing is never returned while an unresolved one exists -
and the fallback is *tactically safe*: it avoids an immediate loss whenever
an avoiding move exists. That is a one-ply guarantee, not a game-theoretic
one: a drawish position can still be turned into a forced loss by the
fallback, as long as the loss takes more than one ply to land.

Below `EXACT_SOLVE_MIN_PLIES` (14) the tier does not spend the full
budget: shallow positions almost never fit an interactive weak solve, so
they are only probed with `OPENING_PROBE_BUDGET` (50 ms) - deliberately
not a bypass, because rare shallow positions are provable in milliseconds
and "proven-optimal whenever the proof fits" must hold for them too.

The benchmark data behind this design
(`python scripts/benchmark_search.py --skip-solver` off, agent-like config
- 3s budget, TT 2^21, sampled ply depths including 13, move sequences
printed per row):

- weak-solve cost is *position-dependent, not monotonic in ply*: one
  13-ply position solved in 0.03s, a 14-ply one needed 9.5s, a 16-ply one
  timed out while an 18-ply one took 3 nodes. No ply floor can bound the
  response time - only the time budget can, which is exactly what
  `solve_root` guarantees;
- the empty board answers via the fallback (center column) within the
  budget, meeting the "interactive from move one" requirement.

Native-backend decision: a C++/pybind11 solver (or the public 8-ply
opening databases) would push proven-optimal play into the deep opening.
The anytime tier is already interactive, but the fallback can still
squander winnable positions (one-ply safety only), so the native backend
stays on the roadmap; an exact oracle - the solver itself on deep
positions, or an opening database - is the right tool to measure how much
that actually costs in strength.

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
