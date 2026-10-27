<p align="center">
  <img src="https://raw.githubusercontent.com/tzii/Pefforza_4/main/assets/pefforza4-banner.png" alt="Pefforza 4 - Connect 4, AI, vision, and voice" width="100%">
</p>

<h1 align="center">Pefforza 4</h1>

<p align="center">
  <strong>Connect Four powered by perfect play, computer vision, and voice interaction.</strong>
</p>

<p align="center">
  <a href="https://github.com/tzii/Pefforza_4/actions/workflows/ci.yml">
    <img src="https://github.com/tzii/Pefforza_4/actions/workflows/ci.yml/badge.svg" alt="CI status">
  </a>
  <img src="https://img.shields.io/badge/Python-3.10--3.13-3776AB?logo=python&logoColor=white" alt="Python 3.10 to 3.13">
  <img src="https://img.shields.io/badge/license-AGPL--3.0-blue" alt="AGPL-3.0 license">
</p>

<p align="center">
  <a href="https://tzii.github.io/Pefforza_4/">Project website &amp; demo</a> &bull;
  <a href="#quick-start">Quick start</a> &bull;
  <a href="#play">Play</a> &bull;
  <a href="#how-strong-is-each-tier">Strength</a> &bull;
  <a href="https://github.com/tzii/Pefforza_4/blob/main/docs/PROJECT_DEEP_DIVE.md">Technical docs</a>
  (<a href="https://github.com/tzii/Pefforza_4/blob/main/docs/it/PROJECT_DEEP_DIVE.md">italiano</a>)
</p>

Pefforza 4 turns Connect Four into a complete AI project. A webcam finds a
real 6x7 board on its own and reads it, the agent chooses a move, and an
augmented-reality overlay shows the recommendation while optional
text-to-speech comments on the game. The same engine also runs without
hardware in a terminal or Pygame GUI.

## Features

- **Perfect play** - the `impossible` tier combines an exact opening book
  (every position it can reach up to ply 17, generated offline by a native
  solver) with an exact solver, and is graded move by move against an
  independent oracle: 100% of its moves keep the game-theoretic outcome.
- **Five AI levels** - random, a 1-ply heuristic, bitboard alpha-beta, the
  perfect tier, and a convolutional network distilled from exact solver
  labels.
- **Computer vision** - automatic board localization from the lattice of
  holes, HSV classification that adapts to the room's lighting, and a
  validator that never lets a misread (a hand, a falling token) reach the AI.
- **Voice interaction** - non-blocking, fail-soft commentary via `pyttsx3`
  automatically disables itself if audio is unavailable.
- **Three play modes** - terminal CLI, Pygame GUI, or an AR assistant for a
  real board (on demand or continuously watching).

## Quick start

```bash
git clone https://github.com/tzii/Pefforza_4.git
cd Pefforza_4
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
pip install -e ".[dev]"
pefforza-gui --difficulty impossible
```

Run the activation command for your operating system, then continue with the
installation and launch commands.

## Architecture

![Pefforza project structure](https://raw.githubusercontent.com/tzii/Pefforza_4/main/assets/structure.png)

### Project layout

- `pefforza/` — installable package
  - `constants.py`, `rules.py` — board geometry and pure game logic (no heavy deps).
  - `cli/` — entrypoints (`play_cli`, `play_gui`, `play_physical`).
  - `agent/difficulty.py` — the difficulty tier registry.
  - `agent/search/` — bitboards, the `hard` alpha-beta engine, the exact solver and the opening book.
  - `agent/oracle.py` — exact-oracle grading of any agent.
  - `agent/data/` — the opening book and the oracle set; `agent/models/` — the neural checkpoint.
  - `agent/networks.py`, `agent/train.py` — CNN policy, solver distillation and PPO.
  - `envs/connect4_env.py` — Gymnasium environment.
  - `vision/` — board localization, adaptive classification, reading validation, diagnostics.
  - `interaction/voice.py` — thread-safe TTS wrapper.
- `play_cli.py`, `play_gui.py`, `play_physical.py`, `main.py` — thin shims so `python play_cli.py` keeps working; `main.py` runs the physical assistant in watch mode with voice.
- `scripts/` — offline tooling: native-solver wrapper, book / oracle / teacher-data builders, benchmarks.
- `notebooks/` — exploratory work (training demo, vision debugging, etc.).
- `tests/` — headless pytest suite (no camera, audio, or trained model needed).

## Requirements

- Python 3.10 – 3.13
- No C/C++ toolchain is needed; SB3 brings PyTorch (CPU is enough for inference and training).

## Install

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Editable install with dev tooling
pip install -e ".[dev]"
```

If you prefer plain requirements files:

```bash
pip install -r requirements-dev.txt   # runtime + dev
# or, runtime only
pip install -r requirements.txt
```

## Play

The opponent is selectable via `--difficulty`:

| Tier | Engine | Notes |
|---|---|---|
| `easy` | random | Picks any legal column |
| `medium` | 1-ply heuristic | Win-if-you-can, block-if-you-must, prefer center |
| `hard` (default) | bitboard alpha-beta depth 8 | Same heuristic as the matrix baseline, an order of magnitude faster |
| `impossible` | opening book + exact solver (~3s) | Perfect: book moves up to ply 17, then every move proven; tactically-safe fallback only for off-book positions it cannot prove |
| `neural` | CNN distilled from exact solver labels | The network's own judgment, no search |

### How strong is each tier?

Every tier graded against the exact oracle - 729 positions with the native
solver's score for every column - by
`python -m pefforza.agent.evaluate --oracle --difficulty <tier>`. A move is
*value-preserving* if it keeps the game-theoretic outcome (won stays won,
drawn stays drawn) and *exactly optimal* if it also wins fastest or loses
slowest. "Game lines" are the 546 positions from games the graded side plays
perfectly; "all" adds off-book positions from two noisy players.

| Tier | Value-preserving (game lines) | Value-preserving (all) | Exactly optimal (all) |
|---|---:|---:|---:|
| `impossible` | **100%** | 98.4% | 89.7% |
| `neural` | 96.3% | 95.5% | 87.5% |
| `hard` | 90.8% | 90.5% | 78.2% |
| `medium` | 77.5% | 79.1% | 56.5% |
| `easy` | 65.6% | 66.1% | 30.0% |

The distilled network plays without any search, yet ranks between `hard`
and `impossible`: head to head it draws `hard` with either color, wins
200/200 games against the previous checkpoint (PPO against a random
opponent, which scored 59.7% / 61.0% / 31.3%) and never loses to depth-4
minimax. Details: [search engine notes](https://github.com/tzii/Pefforza_4/blob/main/docs/search_engine.md).

### Terminal

After any `pip install` (editable or from a wheel), the console command is
`pefforza-cli`; the repo-root script works too:

```bash
pefforza-cli                                        # default: hard
python play_cli.py --difficulty impossible          # perfect play
python play_cli.py --difficulty medium --voice      # easier opponent + TTS
python play_cli.py --difficulty neural --model my.zip
```

### Pygame GUI

```bash
pefforza-gui --difficulty impossible
# or, from a source checkout:
python play_gui.py --difficulty impossible
```

### Physical board (AR assistant)

```bash
pefforza-physical                                    # default: hard, on demand
pefforza-physical --difficulty impossible --watch --voice
pefforza-physical --difficulty medium --ai-color yellow --camera 0
```

When the camera window opens, the board is located automatically and
outlined - press `ENTER` to accept it, or click its four corners (any order)
to set them by hand. Then press `SPACE` to analyse the current board (or use
`--watch` to analyse continuously: a reading is used once it has been
stable for a few frames, and each new recommendation is announced once).
`r` resets board tracking, `q` quits. Every reading is validated (gravity,
turn order, game history) before the AI sees it, and validated readings
re-fit the color thresholds to the current lighting.

The camera feed is mirrored for a natural experience, so the arrow is drawn
in display space while the printed/spoken recommendation is translated to
the physical board's column numbering (what you count on the real board,
left to right).

`python main.py` is a shortcut for `pefforza-physical --watch --voice
--ai-color yellow` (extra arguments are forwarded, e.g. `--no-voice`).

### Verify the vision pipeline

If physical-board play feels off, check what the detector actually sees:

```bash
python -m pefforza.vision.diagnose             # default camera 0
python -m pefforza.vision.diagnose --camera 1
python -m pefforza.vision.diagnose --flip      # mirror feed first
```

After calibration the tool overlays each detected cell with `X`/`O`/`.` and a
confidence value (0–1). If empty cells show high confidence, lighting is too
dim or your color thresholds need adjusting; if tokens show low confidence,
the camera is glaring or the ROI margin is wrong. Press `s` to save a
`vision_debug.png` snapshot for sharing or further analysis.

Headless vision tests (no camera needed) render boards into cluttered scenes
under perspective and dim light. To regression-test your own setup, drop a
frame and its labels into `tests/fixtures/vision/` (see
`tests/test_vision_auto.py`).

## Train

The bundled `neural` checkpoint is distilled from exact solver labels:

```bash
# Supervised distillation from solver-labelled positions
python -m pefforza.agent.train --teacher teacher.npz --epochs 12 --out model.zip

# Optional PPO fine-tuning (plays both colors) against a chosen opponent
python -m pefforza.agent.train --init model.zip --opponent heuristic --timesteps 200000
```

`teacher.npz` comes from `scripts/build_teacher_set.py`, which needs Pascal
Pons' native solver - see [CONTRIBUTING.md](https://github.com/tzii/Pefforza_4/blob/main/CONTRIBUTING.md#regenerating-bundled-data).
Or open `notebooks/04_improve_model.ipynb` for an interactive training loop.

## Evaluate

```bash
# Grade any tier or checkpoint move by move against the exact oracle
python -m pefforza.agent.evaluate --oracle --difficulty impossible
python -m pefforza.agent.evaluate --oracle --model my.zip

# Matches (sides alternate so first-mover bias doesn't mislead you)
python -m pefforza.agent.evaluate --difficulty neural --opponent heuristic --games 100
python -m pefforza.agent.evaluate --model new.zip --opponent model --opponent-model old.zip --games 200
```

## Develop

### Project website

The [GitHub Pages showcase](https://tzii.github.io/Pefforza_4/) lives in
[`website/`](https://github.com/tzii/Pefforza_4/blob/main/website/README.md).
It includes a scroll-driven project tour and a standalone browser Connect
Four demo. Requires Node.js 22.13 or later:

```bash
cd website
npm ci
npm run dev
```

Run `npm test`, `npm run typecheck`, `npm run lint`, and `npm run build:pages` in that
directory to validate the Pages export. Website changes on `main` deploy through
the `Project website` GitHub Actions workflow. The browser demo is independent of the full Python
solver and PPO agent; camera and voice features remain in the Python application.

### Python quality gates

Run the quality gates before pushing:

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest --cov=pefforza
```

CI runs the same checks on Python 3.10–3.13 (Ubuntu) plus Windows and macOS,
enforces a coverage floor, and smoke-tests the built wheel. Changes are
tracked in [CHANGELOG.md](https://github.com/tzii/Pefforza_4/blob/main/CHANGELOG.md);
pushing a `vX.Y.Z` tag publishes a release (see
[CONTRIBUTING.md](https://github.com/tzii/Pefforza_4/blob/main/CONTRIBUTING.md#releasing)).

## Conventions

Player IDs in the environment use **`1` for the agent's perspective and `2`
for the opponent**. The vision pipeline uses **`1 = Red`, `2 = Yellow`**. When
the AI plays Yellow, translate between the two views with
`pefforza.rules.swap_perspective`.

## License

Released under the [GNU Affero General Public License v3.0 or later](https://github.com/tzii/Pefforza_4/blob/main/LICENSE).
See `LICENSE` for the full text. The bundled opening book and oracle set were
generated with [Pascal Pons' Connect Four solver](https://github.com/PascalPons/connect4)
(AGPL-3.0). Contributor guidance lives in
[CONTRIBUTING.md](https://github.com/tzii/Pefforza_4/blob/main/CONTRIBUTING.md) and
[AGENTS.md](https://github.com/tzii/Pefforza_4/blob/main/AGENTS.md).
