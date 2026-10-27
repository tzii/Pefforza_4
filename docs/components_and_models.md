# Repository Map, Components and Domain Model

> 🇮🇹 [Versione italiana](it/components_and_models.md)

This module details how the repository is organized, the classes and
functions of each logical block, and the data structures that model the
game.

---

## 1. Repository map

| Path | Kind | Role | Notes |
|:---|:---|:---|:---|
| `pefforza/` | Folder | Main Python package | All importable core modules. |
| [pefforza/constants.py](../pefforza/constants.py) | File | Single source of truth for geometry | `ROWS`, `COLS`, `WIN_LENGTH`, player IDs, model path. |
| [pefforza/rules.py](../pefforza/rules.py) | File | Pure game logic | Board functions with no heavy dependencies. |
| `pefforza/agent/` | Folder | Decision engines | Tiers, search, training, evaluation. |
| [pefforza/agent/difficulty.py](../pefforza/agent/difficulty.py) | File | Difficulty registry | Maps tier names to agent factories. |
| [pefforza/agent/minimax.py](../pefforza/agent/minimax.py) | File | Matrix negamax baseline + safety net | Correctness reference for the bitboard engines. |
| [pefforza/agent/search/](../pefforza/agent/search/) | Folder | Bitboard engines | `BitPosition`, the `hard` alpha-beta engine, `PerfectSolver`, `OpeningBook`. |
| [pefforza/agent/oracle.py](../pefforza/agent/oracle.py) | File | Exact oracle evaluation | Grades any agent move by move against solver scores. |
| `pefforza/agent/data/` | Folder | Bundled data | `opening_book.xz` (533k positions), `oracle_positions.json` (729 positions). |
| [pefforza/agent/networks.py](../pefforza/agent/networks.py) | File | Neural network trunk | `Connect4CNN`, an SB3 features extractor. |
| [pefforza/agent/train.py](../pefforza/agent/train.py) | File | Training | Solver distillation and PPO (both colors, selectable opponent). |
| [pefforza/agent/evaluate.py](../pefforza/agent/evaluate.py) | File | Headless evaluation | Matches between agents, oracle grading, tier comparison. |
| [pefforza/envs/connect4_env.py](../pefforza/envs/connect4_env.py) | File | Gymnasium `Connect4Env` | State transitions, rewards, legal actions. |
| [pefforza/interaction/voice.py](../pefforza/interaction/voice.py) | File | Non-blocking voice engine | Async queue, `pyttsx3` / `NullBackend` backends. |
| [pefforza/vision/board_detector.py](../pefforza/vision/board_detector.py) | File | Board detection and classification | Automatic localization, warp, adaptive HSV classification. |
| [pefforza/vision/validation.py](../pefforza/vision/validation.py) | File | Reading validation | Gravity, turn order, outcome and history checks. |
| [pefforza/vision/diagnose.py](../pefforza/vision/diagnose.py) | File | Live diagnostic tool | Per-cell labels and confidences on the live feed. |
| [pefforza/cli/](../pefforza/cli/) | Folder | Entrypoint implementations | `play_cli`, `play_gui`, `play_physical` (console scripts). |
| `play_cli.py`, `play_gui.py`, `play_physical.py`, [main.py](../main.py) | Files | Repo-root shims | Keep `python play_cli.py` working; `main.py` = physical `--watch --voice`. |
| [scripts/](../scripts/) | Folder | Offline tooling | Native-solver wrapper, book/oracle/teacher builders, benchmarks. |
| `tests/` | Folder | Unit, behavioral and end-to-end tests | Headless: no camera, audio or trained model needed. |
| [pyproject.toml](../pyproject.toml) | File | Project and tool configuration | Metadata, dependencies, ruff, mypy, pytest, coverage. |

---

## 2. Component breakdown

### `Connect4Env`

* **File**: [pefforza/envs/connect4_env.py](../pefforza/envs/connect4_env.py)
* **Responsibility**: a Gymnasium-compliant environment with `reset()` and
  `step()`.
* **Main API**: `Connect4Env(gym.Env)`; `step(action)` plays a column,
  hands the turn over, assigns rewards and detects the end of the game;
  `valid_action_mask()` returns the legal columns.
* **Input / output**: an integer action (0-6) / observation (`Board`),
  reward, terminated, truncated, info.
* **Error handling**: out-of-range actions or full columns return a `-10.0`
  penalty and end the episode.
* **Side effects**: mutates `self.board` and `self.current_player`.

### `BoardDetector` and `locate_board`

* **File**: [pefforza/vision/board_detector.py](../pefforza/vision/board_detector.py)
* **Responsibility**: find the board, normalize the image and classify the
  tokens.
* **Main API**:
  * `locate_board(frame)`: finds the non-blue holes enclosed by the board's
    blue outline, fits the 6 x 7 lattice through the corner holes, verifies
    that the lattice predicts the detected holes, and returns the four
    playing-area corners (or `None`).
  * `calibrate(cap, flip, auto=True)`: outlines the detected board (ENTER
    accepts) or takes four clicked corners in any order; `set_corners()`
    computes the warp.
  * `classify_board_image(img)` / `cell_confidences(img)`: per-cell
    classification and fill ratios, using the detector's `ColorProfile`.
  * `adapt_colors(img, grid)`: re-fits the red/yellow hue bands and S/V
    floors to a trusted reading; commits the new profile only if it
    reproduces that reading exactly.
  * `physical_col(display_col)`: maps the mirrored display column to the
    physical one.
* **Technical notes**: cell ROIs are inset by 20% (`_CELL_MARGIN_FRAC`) to
  ignore the plastic frame; red uses two hue ranges because it wraps around
  0/180.

### `BoardStateValidator`

* **File**: [pefforza/vision/validation.py](../pefforza/vision/validation.py)
* **Responsibility**: accept only physically and temporally plausible
  readings - gravity, red-first counts, a consistent outcome, and a legal
  transition (one drop or one full round) from the last accepted state; a
  cleared board after a finished game starts a new game.

### `PhysicalAssistant` and `StableGridFilter`

* **File**: [pefforza/cli/play_physical.py](../pefforza/cli/play_physical.py)
* **Responsibility**: the camera-free decision path of the AR assistant
  (validate, detect game over, wait for the opponent, ask the agent) and
  the `--watch` debouncer that emits a reading only after it has been
  identical for N frames.

### Search engines

* **Files**: [pefforza/agent/search/](../pefforza/agent/search/) and
  [pefforza/agent/minimax.py](../pefforza/agent/minimax.py); details in
  [search_engine.md](search_engine.md).
* `BitboardSearchAgent`: depth-8 alpha-beta with a transposition table, the
  `hard` tier, pinned to the matrix baseline by differential tests.
* `PerfectSolver`: exact win/draw/loss solver; `solve_root` proves root
  moves in interleaved rounds under a time budget.
* `OpeningBook`: strongly optimal moves for every position the AI can reach
  up to ply 17, keyed by symmetry-canonical bitboard keys.
* `tactical_safety_net(agent)`: wraps an agent so it always takes an
  immediate win or blocks an immediate threat.

### Neural tier

* **Files**: [networks.py](../pefforza/agent/networks.py),
  [train.py](../pefforza/agent/train.py)
* `Connect4CNN` turns the board into self/opponent/empty planes and applies
  3 x 3 convolutions; it is the shared trunk of an ordinary SB3 `PPO`
  policy, so checkpoints load with `PPO.load`.
* `distill()` trains the policy on the distribution of exactly optimal
  columns and the value head on the game outcome, from solver-labelled
  positions; `SinglePlayerWrapper` + `train()` fine-tune with PPO.
* At play time `model_agent` masks full columns out of the policy.

### `VoiceEngine`

* **File**: [pefforza/interaction/voice.py](../pefforza/interaction/voice.py)
* **Responsibility**: asynchronous text-to-speech that never slows the game.
* **Main API**: `speak(text)` queues a phrase; `play_move_commentary(col,
  confidence)` builds a move comment; `shutdown()` drains the worker.
* **Design**: producer-consumer over a thread-safe queue. If `pyttsx3`
  fails to initialize or there is no audio device, the engine disables
  itself (fail-soft); `PEFFORZA_TTS_BACKEND=null` forces the silent backend.

---

## 3. Domain / data model

No database is needed: data lives in memory as typed NumPy arrays,
bitboard integers and dataclasses.

### Board (`rules.Board`)

A 6 x 7 NumPy `int8` array.

| Cell | Meaning | Encoding |
|:---|:---|:---|
| `board[r, c] == 0` | Empty | `EMPTY` |
| `board[r, c] == 1` | Player 1 | The agent itself (agent view) / red (vision view) |
| `board[r, c] == 2` | Player 2 | The opponent (agent view) / yellow (vision view) |

### `BitPosition`

Seven bits per column (six cells plus a sentinel). `current` holds the
stones of the side to move, `mask` all stones; `key = current + mask` and
`canonical_key = min(key, mirrored key)` index the transposition table and
the opening book.

### Oracle position

`OraclePosition(moves, scores, source)`: a move sequence and the exact
score of every column from the side to move (`0` draw, `s > 0` win with `s`
of the mover's stones left in hand, `s < 0` loss, `None` full column);
`source` is `line` or `random`.

### `RootResult` / `SearchResult`

`RootResult(move, outcome, proven, nodes, elapsed)` reports the exact
solver's choice and whether it carries a proof (`win_now`, `proven_win`,
`proven_draw`, `all_lost`) or is the timeout `fallback`.
`SearchResult(column, score, depth, nodes, elapsed)` profiles the matrix
baseline search.

---

## 4. Concept index

| Concept | Files | Explanation |
|:---|:---|:---|
| **Game geometry** | [constants.py](../pefforza/constants.py) | Board size and cell encodings. |
| **Rules and wins** | [rules.py](../pefforza/rules.py) | Horizontal, vertical and diagonal four-in-a-row detection. |
| **RL environment** | [connect4_env.py](../pefforza/envs/connect4_env.py) | States, actions and rewards for Gymnasium. |
| **Perfect play** | [search/perfect.py](../pefforza/agent/search/perfect.py), [search/book.py](../pefforza/agent/search/book.py) | Exact solver and opening book behind `impossible`. |
| **Measuring perfection** | [oracle.py](../pefforza/agent/oracle.py) | Value-preserving and exactly-optimal move rates per tier. |
| **Perspective rectification** | [board_detector.py](../pefforza/vision/board_detector.py) | Automatic or manual corners, homography warp. |
| **Color recognition** | [board_detector.py](../pefforza/vision/board_detector.py) | Adaptive HSV thresholds and fill ratios. |
| **Reading validation** | [validation.py](../pefforza/vision/validation.py) | Rejects implausible readings before the AI sees them. |
| **Threaded speech queue** | [voice.py](../pefforza/interaction/voice.py) | Daemon worker keeps speech off the game thread. |
