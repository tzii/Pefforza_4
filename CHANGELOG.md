# Changelog

All notable changes to Pefforza are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Releases are tagged `vX.Y.Z`;
pushing a tag publishes to PyPI (see [Releasing](CONTRIBUTING.md#releasing)).

## [Unreleased]

## [0.6.0] - Unreleased

### Added

- **Perfect `impossible` tier.** An exact opening book
  (`pefforza/agent/data/opening_book.xz`, 533k positions, 950 KiB) gives a
  strongly optimal move for every position the AI can reach up to ply 17,
  for both colors; past the book the exact solver proves every move. On
  the oracle set's game lines the tier is 100% value-preserving.
- **Exact oracle evaluation** (`pefforza.agent.oracle`,
  `python -m pefforza.agent.evaluate --oracle --difficulty <tier>`): grades
  every move of any tier or checkpoint against native-solver scores for all
  columns of 729 bundled positions.
- `--difficulty` for `pefforza.agent.evaluate`, so tiers can be compared
  head to head as well as checkpoints.
- **`pefforza-physical` console script** with a `--watch` mode (continuous,
  debounced analysis through the same validator and difficulty tiers) and
  `--voice`.
- **Automatic board localization**: calibration finds the 6x7 hole lattice
  of the blue frame; ENTER accepts the outline (clicking corners still works).
- **Lighting adaptation**: every validated reading re-fits the HSV
  thresholds (`BoardDetector.adapt_colors`, `ColorProfile`), committed only
  when the new profile reproduces the reading exactly.
- Solver-distillation training (`python -m pefforza.agent.train --teacher`)
  with a convolutional policy (`pefforza.agent.networks.Connect4CNN`); PPO
  training now plays both colors, takes `--opponent` and `--init`.
- Offline data tooling in `scripts/`: `build_opening_book.py`,
  `build_oracle_set.py`, `build_teacher_set.py` (Pascal Pons' solver).
- Windows and macOS CI legs, a coverage ratchet (`fail_under`), headless
  end-to-end tests of the CLI, GUI and physical game loops, and a PyPI
  release workflow.

### Changed

- The bundled `neural` checkpoint is a CNN distilled from exact solver labels
  instead of an MLP trained with PPO against a random opponent: 96.3% (was
  59.7%) value-preserving moves on the oracle's game lines; it beats the old
  checkpoint 200-0 and draws `hard` with either color.
- The `neural` tier masks full columns out of the policy distribution
  instead of falling back to the first legal column.
- `PerfectSolver.solve_root` proves root moves in interleaved rounds, so a
  cheap winning proof is no longer starved by expensive refutations.
- `main.py` is now a shim for `pefforza-physical --watch --voice --ai-color
  yellow`; it previously ran its own PPO-only loop.
- `SinglePlayerWrapper` observations are always from the agent's perspective
  and the agent plays second half of the time (was: always first).

## [0.5.0] - 2026-09-02

### Added

- Exact bitboard `impossible` tier with the anytime `solve_root` strategy;
  hardened to never return a refuted root move.

## [0.4.0] - 2026-09-02

### Added

- `PerfectSolver` phase 2: threat pruning, symmetry-canonical fixed-size
  transposition table, winning-spot move ordering.

## [0.3.0] - 2026-09-01

### Added

- Board-state validation for webcam readings (`BoardStateValidator`) and
  physical turn detection.
- Bitboard alpha-beta backend for the `hard` tier.

## [0.2.0] - 2026-09-01

### Added

- Installable package, console entrypoints, CI, and the bundled PPO
  checkpoint.

[Unreleased]: https://github.com/tzii/Pefforza_4/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/tzii/Pefforza_4/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/tzii/Pefforza_4/releases/tag/v0.5.0
[0.4.0]: https://github.com/tzii/Pefforza_4/releases/tag/v0.4.0
[0.3.0]: https://github.com/tzii/Pefforza_4/releases/tag/v0.3.0
[0.2.0]: https://github.com/tzii/Pefforza_4/releases/tag/v0.2.0
