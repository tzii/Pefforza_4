# Public Interfaces, Configuration and Dependencies

> 🇮🇹 [Versione italiana](it/interfaces_and_config.md)

This module documents every way to drive Pefforza (CLI/GUI/AR), the
available configuration and the software dependencies.

---

## 1. Commands

After `pip install -e .` (or a wheel install) the console scripts are on the
`PATH`; the repo-root scripts work from a source checkout.

| Command | Purpose | Key arguments | Implementation |
|:---|:---|:---|:---|
| `pefforza-cli` / `python play_cli.py` | Text game in the terminal | `--difficulty` (easy, medium, hard, impossible, neural), `--voice`, `--model`, `--seed` | [play_cli.py](../pefforza/cli/play_cli.py) |
| `pefforza-gui` / `python play_gui.py` | Pygame game | `--difficulty`, `--no-animate`, `--model`, `--seed` | [play_gui.py](../pefforza/cli/play_gui.py) |
| `pefforza-physical` / `python play_physical.py` | AR assistant for a physical board | `--difficulty`, `--ai-color` (red, yellow), `--camera`, `--watch`, `--stable-frames`, `--voice`/`--no-voice`, `--model`, `--seed` | [play_physical.py](../pefforza/cli/play_physical.py) |
| `python main.py` | Continuous AR assistant (= `pefforza-physical --watch --voice --ai-color yellow`) | any `pefforza-physical` argument, e.g. `--no-voice` | [main.py](../main.py) |
| `python -m pefforza.vision.diagnose` | Live vision diagnostics | `--camera`, `--flip` | [diagnose.py](../pefforza/vision/diagnose.py) |
| `python -m pefforza.agent.evaluate` | Matches, tier comparison, oracle grading | `--difficulty`, `--model`, `--opponent` (random, heuristic, minimax, self, model), `--games`, `--oracle`, `--oracle-source` (all, line, random) | [evaluate.py](../pefforza/agent/evaluate.py) |
| `python -m pefforza.agent.train` | Solver distillation or PPO training | `--teacher`, `--epochs`, `--out`; PPO: `--timesteps`, `--iterations`, `--opponent` (random, heuristic, hard), `--init` | [train.py](../pefforza/agent/train.py) |
| `python scripts/build_opening_book.py` | Regenerate the opening book (native solver) | `--solver`, `--max-ply` | [script](../scripts/build_opening_book.py) |
| `python scripts/build_oracle_set.py` | Regenerate the oracle set | `--solver`, `--seed` | [script](../scripts/build_oracle_set.py) |
| `python scripts/build_teacher_set.py` | Generate distillation data | `--solver`, `--games`, `--out` | [script](../scripts/build_teacher_set.py) |
| `python scripts/benchmark_search.py` | Search-engine benchmarks | see `--help` | [script](../scripts/benchmark_search.py) |

### Physical assistant controls

| Key | Effect |
|:---|:---|
| ENTER / `a` (calibration) | Accept the automatically detected board |
| Mouse clicks (calibration) | Set the four corners manually, any order |
| SPACE | Analyze the current board (on-demand mode) |
| `r` | Reset board tracking (start a new history) |
| `q` | Quit |

---

## 2. Configuration and environment

| Setting | Where | Default | Description |
|:---|:---|:---|:---|
| `PEFFORZA_TTS_BACKEND` | Environment variable | empty (use `pyttsx3`) | `null` forces the silent `NullBackend`. |
| `SDL_VIDEODRIVER` | Environment variable | platform default | `dummy` runs Pygame headless (used by the tests). |
| `ROWS`, `COLS`, `WIN_LENGTH` | [constants.py](../pefforza/constants.py) | `6`, `7`, `4` | Board geometry; code-only. |
| `DEFAULT_MODEL_PATH` | [constants.py](../pefforza/constants.py) | `pefforza/agent/models/notebook_model.zip` | Bundled neural checkpoint. |
| `IMPOSSIBLE_TIME_BUDGET` | [difficulty.py](../pefforza/agent/difficulty.py) | `3.0` s | Solver budget past the opening book. |
| `HARD_BITBOARD_DEPTH` | [difficulty.py](../pefforza/agent/difficulty.py) | `8` | Search depth of the `hard` tier. |
| `DEFAULT_BOOK_PATH` | [search/book.py](../pefforza/agent/search/book.py) | `pefforza/agent/data/opening_book.xz` | Missing or corrupt book: warning, search fallback. |
| `ColorProfile` | [board_detector.py](../pefforza/vision/board_detector.py) | indoor-lighting HSV bands | Per-detector thresholds; adapted at runtime. |

---

## 3. Dependencies

Everything runs locally; no cloud service is used.

| Dependency | Usage | Importance | If removed |
|:---|:---|:---|:---|
| `numpy` | All board arrays, book lookup | Critical | Nothing works. |
| `opencv-python` | Camera, board localization, warp, HSV classification, overlays | Critical for AR | No physical-board mode; CLI and GUI still work. |
| `stable-baselines3` (+ PyTorch) | `PPO` inference and training for the `neural` tier | High | `neural` falls back to the heuristic; training unavailable. |
| `gymnasium` | `Connect4Env` | High | No environment for training. |
| `pygame` | GUI rendering and animations | High | No GUI; CLI still works. |
| `pyttsx3` | Offline speech | Medium | No speech (fail-soft). |

Dev-only: `pytest`, `pytest-cov`, `ruff`, `mypy`. Offline data generation
additionally needs Pascal Pons' native solver (AGPL-3.0); see
[scripts/native_solver.py](../scripts/native_solver.py).
