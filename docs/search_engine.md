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
  scores. It is currently intended for validated late/mid-game positions and
  is not yet wired to the public `impossible` tier.

The exact solver still needs stronger move ordering and an opening-book/native
backend decision before it can guarantee interactive response times from the
initial position.

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
