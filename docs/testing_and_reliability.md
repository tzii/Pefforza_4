# Testing Strategy, Error Handling and Reliability

> 🇮🇹 [Versione italiana](it/testing_and_reliability.md)

How Pefforza is tested, how runtime errors are contained, and the
reliability and safety considerations behind the design.

---

## 1. Testing strategy

The suite uses `pytest` with coverage (`pytest-cov`). Every test is
**headless**: no webcam, audio device, display or trained model is needed.
Pygame runs on SDL's dummy driver, human input is scripted, and the camera
is replaced by fakes or by boards rendered in code.

```bash
python -m pytest --cov=pefforza
```

CI runs the suite with ruff and mypy on Python 3.10-3.13 (Ubuntu) plus
Windows and macOS, and enforces a coverage floor (`fail_under` in
`pyproject.toml`, a ratchet that only goes up). A separate job builds the
wheel, installs it in a clean venv and checks the console scripts, the
bundled checkpoint and the opening book.

### Test files

| Test file | Area | What it checks |
|:---|:---|:---|
| [test_rules.py](../tests/test_rules.py) | Pure game logic | Wins in all directions, full columns, perspective swap. |
| [test_connect4_env.py](../tests/test_connect4_env.py) | Gymnasium env | `step()`, illegal-move penalty, wins and draws. |
| [test_minimax.py](../tests/test_minimax.py) | Matrix baseline | Fixed-depth search, time budget, iterative deepening. |
| [test_bitboard_search.py](../tests/test_bitboard_search.py) | `hard` engine | Differential tests against the matrix baseline (same score and move), with/without TT, under mirroring. |
| [test_perfect_solver.py](../tests/test_perfect_solver.py), [test_exact_agent.py](../tests/test_exact_agent.py) | Exact solver | Exact scores, threat pruning, symmetry, anytime `solve_root` guarantees. |
| [test_opening_book.py](../tests/test_opening_book.py) | Opening book | Format round trip, mirrored lookups, corruption handling, **closure** (following its own book the AI never leaves it before ply 17, whatever the opponent plays), tier wiring. |
| [test_oracle.py](../tests/test_oracle.py) | Exact oracle | Well-formed set, **every book move exactly optimal** against independent scores, `impossible` perfect on the endgame slice, CLI. |
| [test_blocks_threats.py](../tests/test_blocks_threats.py) | Tactical safety | `medium`, `hard` and `impossible` always block a three or take an immediate win. |
| [test_difficulty.py](../tests/test_difficulty.py), [test_evaluate.py](../tests/test_evaluate.py), [test_full_game_sim.py](../tests/test_full_game_sim.py) | Tiers and harness | Registry, fallbacks, full simulated games. |
| [test_train.py](../tests/test_train.py) | Neural pipeline | CNN shapes, teacher targets, distillation learns, save/load round trip, both-color wrapper, PPO smoke run. |
| [test_board_detector.py](../tests/test_board_detector.py) | Classification | Synthetic boards at several resolutions, confidences. |
| [test_vision_auto.py](../tests/test_vision_auto.py) | Localization and lighting | Boards rendered into cluttered scenes under perspective: corners found within 15% of a cell, grid read exactly; partial boards rejected; dim light breaks the default thresholds and adaptation recovers; labelled real photos in `tests/fixtures/vision/` are picked up automatically. |
| [test_board_validation.py](../tests/test_board_validation.py) | Reading validation | Gravity, counts, outcomes, transitions, new-game detection. |
| [test_play_physical.py](../tests/test_play_physical.py) | AR assistant | Decision path, debouncing, main loop with a fake camera. |
| [test_game_loops.py](../tests/test_game_loops.py) | CLI and GUI | Full games end to end, watchdog diagnostics. |
| [test_cli.py](../tests/test_cli.py), [test_diagnose.py](../tests/test_diagnose.py), [test_voice.py](../tests/test_voice.py) | Entrypoints, diagnostics, speech | `--help` smoke tests, diagnostic loop, voice queue lifecycle. |

### Measuring perfect play

Beating weaker opponents says little about a near-perfect player, so the
`impossible` tier is graded against an **exact oracle**: 729 positions with
the native solver's score for every column (`pefforza/agent/data/
oracle_positions.json`). For each position the evaluated agent's move is
*value-preserving* if it keeps the game-theoretic outcome and *exactly
optimal* if it also has the best score (fastest win / slowest loss):

```bash
python -m pefforza.agent.evaluate --oracle --difficulty impossible
```

The README reports the current numbers for every tier.

---

## 2. Error handling and edge cases

1. **Fail-soft audio**: `pyttsx3` initialization is wrapped; without an
   audio driver (common on headless Linux or Docker) a warning is logged and
   speech is disabled. A playback error in the worker disables further
   attempts without reaching the game thread.
2. **User input validation**: the CLI and GUI check every human move
   before it reaches `Connect4Env` (which would end the episode with a
   penalty) and ask again.
3. **Untrusted camera readings**: `BoardStateValidator` rejects readings
   that violate gravity, turn order, outcome consistency or the history, so
   a hand over the board never becomes a position; `--watch` additionally
   requires a reading to be stable for several frames.
4. **Self-checking adaptation**: new color thresholds are committed only if
   they reproduce the validated reading exactly.
5. **AI move sanitization**: an agent returning an illegal column is
   replaced by a legal one; the neural tier masks full columns out of its
   policy in the first place.
6. **Fallbacks**: a missing or unreadable `neural` checkpoint (or missing
   `stable-baselines3`) falls back to the heuristic; a missing or corrupt
   opening book logs a warning and the exact solver plays the opening with
   its tactically-safe fallback; board localization that is not confident
   returns `None` and the user clicks the corners.

---

## 3. Security, privacy and reliability

* **Privacy**: video is processed in memory, locally. No frame is uploaded
  or written to disk, except the `vision_debug.png` snapshot the user saves
  explicitly with `s` in the diagnostic tool.
* **Model loading**: Stable-Baselines3 checkpoints are zip files that can
  contain pickled objects; load only checkpoints you trust (the bundled one
  is produced by `scripts/` + `pefforza.agent.train` from this repository).
  The opening book is a plain compressed array file validated on load.
* **Crash prevention**: speech and rendering run in isolated contexts;
  `finally` blocks release the camera, windows and Pygame on every exit
  path.
* **Supply chain**: CI pins third-party actions by commit SHA and runs with
  read-only permissions; releases publish through PyPI Trusted Publishing
  without stored tokens.
