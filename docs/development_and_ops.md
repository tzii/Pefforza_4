# Development Workflow, Examples and Extensions

> 🇮🇹 [Versione italiana](it/development_and_ops.md)

A practical guide for developers who want to install Pefforza locally, follow
a move end to end, and extend the system.

---

## 1. Build, run and development workflow

### Prerequisites

* Python 3.10, 3.11, 3.12 or 3.13.
* No C/C++ compiler is needed: PyTorch and OpenCV ship as prebuilt wheels.
  (Regenerating the bundled data needs a native solver build - see
  [CONTRIBUTING.md](../CONTRIBUTING.md#regenerating-bundled-data).)

### Environment setup

```bash
python -m venv .venv
# Windows (PowerShell / CMD)
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
```

### Run and test

```bash
# Quality gates (CI runs the same)
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest --cov=pefforza

# Play
pefforza-gui --difficulty impossible
pefforza-physical --watch --voice

# Grade a tier against the exact oracle
python -m pefforza.agent.evaluate --oracle --difficulty impossible

# Webcam diagnostics
python -m pefforza.vision.diagnose --camera 0
```

---

## 2. End-to-end example

A recommendation in the AR assistant, on demand
(`pefforza-physical --ai-color yellow --difficulty impossible`; the AI plays
yellow, the human red):

1. **Calibration**: the board is outlined automatically from the lattice of
   its holes; the user presses ENTER.
2. **Input**: after the human's move lands, the user presses SPACE.
3. **Webcam read**: `play_physical` grabs the current frame (e.g.
   1280 x 720) and mirrors it (`cv2.flip(frame, 1)`) so the screen behaves
   like a mirror.
4. **Warping**: `BoardDetector.process_frame` applies the calibration
   homography and produces a rectified 700 x 600 image.
5. **Classification**: `classify_board_image` reads every cell with the
   current (possibly adapted) color profile. In display coordinates it finds
   red tokens in columns 2, 3 and 4 of the bottom row, yellow in column 1
   and on top of column 3:
   ```
   [[0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0],
    [0,0,0,2,0,0,0],
    [0,2,1,1,1,0,0]]
   ```
6. **Validation**: gravity holds, red has 3 tokens and yellow 2 (yellow to
   move), and the reading follows legally from the last accepted state - it
   is accepted, and the color thresholds are re-fitted to it.
7. **Perspective**: the AI plays yellow (vision id 2), so `swap_perspective`
   turns yellow into `1` (self) and red into `2` (opponent).
8. **Decision**: red threatens to complete the bottom row in display column
   5 (column 1 is already blocked by yellow). The tactical safety net sees
   the immediate threat and returns column 5 - which is also what the exact
   solver would play, since every other move loses at once.
9. **Mirror translation**: the arrow is drawn over display column 5 on the
   mirrored feed; for the human the recommendation is translated with
   `physical_col`: `(7 - 1) - 5 = 1`, i.e. physical column **2**.
10. **Output**: a magenta arrow points into the column on screen, the
    console prints `AI (YELLOW, impossible) recommends physical column 2`,
    and with `--voice` the speech engine says *"Putting in column 2"*.

---

## 3. Extension guide

### A new voice backend (e.g. Piper or a cloud TTS)

1. Open [pefforza/interaction/voice.py](../pefforza/interaction/voice.py).
2. Subclass `TTSBackend`:
   ```python
   class CloudTTSBackend(TTSBackend):
       def __init__(self, api_key: str) -> None:
           self.api_key = api_key  # create the SDK client here

       def speak(self, text: str) -> None: ...  # synchronous API call or local audio streaming

       def close(self) -> None: ...  # release connections
   ```
3. Select it in `VoiceEngine._resolve_backend`, e.g. from an environment
   variable:
   ```python
   if os.environ.get("PEFFORZA_TTS_BACKEND") == "cloud":
       return CloudTTSBackend(api_key=os.environ["TTS_API_KEY"])
   ```
   Keep it fail-soft: an exception must disable speech, never crash the game.

### A new difficulty tier (e.g. MCTS)

1. Implement the agent in `pefforza/agent/mcts.py` as a callable
   `Agent = Callable[[Board, int, list[int]], int]`.
2. Register it in `DIFFICULTIES` in
   [pefforza/agent/difficulty.py](../pefforza/agent/difficulty.py):
   ```python
   "mcts": Difficulty(
       "mcts",
       "Monte Carlo Tree Search, 1000 simulations per move.",
       lambda seed=None: tactical_safety_net(mcts_agent(simulations=1000, seed=seed)),
   )
   ```
3. The tier is immediately available in the CLI, GUI and AR assistant, and
   can be graded with `python -m pefforza.agent.evaluate --oracle
   --difficulty mcts`.

### A better neural checkpoint

1. Generate teacher data with the native solver
   (`scripts/build_teacher_set.py`), or reuse an existing `.npz`.
2. Distill: `python -m pefforza.agent.train --teacher teacher.npz --epochs 12
   --out candidate.zip`; optionally fine-tune with PPO via `--init`.
3. Compare with the oracle and head to head before replacing
   `pefforza/agent/models/notebook_model.zip`:
   ```bash
   python -m pefforza.agent.evaluate --oracle --model candidate.zip
   python -m pefforza.agent.evaluate --model candidate.zip --opponent model \
       --opponent-model pefforza/agent/models/notebook_model.zip --games 200
   ```

### Real webcam regression photos

Save a frame as `tests/fixtures/vision/<name>.png` with a `<name>.json`
holding `{"grid": [[...6 rows of 7...]]}` (and optionally `"corners"`); the
suite then checks automatic localization and classification on it.
