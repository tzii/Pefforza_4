# Search engine

> English only. Panoramica in italiano: [it/components_and_models.md](it/components_and_models.md).

Pefforza keeps a matrix search baseline next to the bitboard engines, and
backs its strongest tier with an exact opening book plus an exact solver.

| Tier | Engine |
|---|---|
| `hard` | `BitboardSearchAgent`, depth-8 alpha-beta with the legacy heuristic |
| `impossible` | `OpeningBook` up to ply 17, then `PerfectSolver.solve_root` (~3 s) |

## Matrix baseline

`pefforza.agent.minimax.MinimaxAgent` is the correctness baseline for the
bitboard engines (and used to back the `impossible` tier with time-budgeted
iterative deepening). Its root alpha-beta handling, mate distance scoring,
and iterative-deepening deadline were corrected before any representation
rewrite.

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

## Exact `impossible` tier and the opening decision (PR5, historical)

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

## Opening book and interleaved proofs (PR8)

PR5 left the opening as the weak spot: with the full 3 s budget, a sample of
game-line positions was proven only 4-56% of the time at plies 8-13 (and the
tier gave those plies a 50 ms probe), and 76-94% at plies 14-17; only from
ply 18 on was every sampled position proven. Two changes close the gap.

**Opening book.** `scripts/build_opening_book.py` enumerates every position
in which the AI is to move up to ply 17 *along the lines it plays itself*:
the AI's move comes from the book, so only the opponent branches. Moves are
strongly optimal (fastest win, slowest loss, else a draw), computed by
Pascal Pons' native solver, with center-first tie-breaking decided in the
canonical orientation so the build is reproducible byte for byte. Both
colors are covered. The result is 533,468 entries in 950 KiB
(`pefforza/agent/data/opening_book.xz`: delta-encoded sorted `uint64` keys,
`int8` moves and scores, xz-compressed). `tests/test_opening_book.py` checks
*closure*: following its own book against arbitrary replies, the AI never
leaves the book before ply 17.

| ply | AI-to-move positions |
|---:|---:|
| 0-10 | 6,397 |
| 11 | 9,155 |
| 12 | 8,007 |
| 13 | 32,069 |
| 14 | 25,835 |
| 15 | 101,195 |
| 16 | 72,779 |
| 17 | 278,031 |

**Interleaved root proofs.** Past the book, `solve_root` used to prove root
moves one after the other. When the only winning move came last in the
order, the budget ran out proving that the other moves lose. Root moves now
get node allowances that grow 4x per round (starting at 2,000 nodes), so the
cheapest proof surfaces first; aborted searches store nothing in the
transposition table and finished subtrees are reused, so the repeated work
stays bounded. The slowest game-line proof in the oracle set dropped from
9.5 s to 2.9 s. Off-book "random" positions can get slower (one went from
9.7 s to 32.7 s unbudgeted), which only matters when the AI joins a game in
progress; the budget still bounds the response time.

## Measuring perfect play: the exact oracle

`pefforza/agent/data/oracle_positions.json` holds 729 positions with the
native solver's score for every column (`scripts/build_oracle_set.py`,
seeded): 546 *line* positions from games where the graded side plays
perfectly (the book where it has an answer) and the opponent half perfectly,
half randomly, and 183 *random* positions from two noisy players.

```bash
python -m pefforza.agent.evaluate --oracle --difficulty impossible
```

| `impossible`, line positions | value-preserving | exactly optimal |
|---|---:|---:|
| plies 0-11 | 100% | 100% |
| plies 12-17 | 100% | 100% |
| plies 18-25 | 100% | 73.3% |
| plies 26-41 | 100% | 72.7% |
| all (546) | **100%** | 93.4% |

Over all 729 positions, including off-book ones, it is 98.4%
value-preserving. Past the book the solver is weak (win / draw / loss), so
a won position always stays won but not always by the fastest route.

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
