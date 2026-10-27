# Pefforza 4 - Presentation Outline

> 🇮🇹 [Versione italiana](it/presentation_outline.md)

## Target audience

- Teachers, classmates and school/university panels.
- People who can program but are not necessarily experts in reinforcement
  learning or computer vision.
- Recruiters and portfolio visitors who want to understand both the result
  and the engineering process.

## Core message

Pefforza 4 is not just a model that picks a column: it is a complete system
that connects a physical board to visual perception, game logic, an exact
solver, a learned policy, augmented reality and spoken feedback. The
project's evolution also teaches an important lesson: "perfect" is a claim
that has to be measured. A neural network can learn a strategy, but a
trustworthy product comes from combining learning, exact algorithms, tests
and diagnostic tools - and checking every move against an oracle.

## Tone and length

- Suggested length: 12-16 minutes, plus a 3-5 minute demo.
- Language: technical but accessible, with specialist terms explained on
  first use.
- Pace: one clear thesis per slide, a dominant visual, details in the
  speaker notes.

## Slide by slide

### 1. Pefforza 4

**Claim:** a physical board becomes an intelligent system.

**Visual:** title slide with a Connect Four board, an AR arrow and summary
metrics.

**Speaker notes:**
- Present the project as an integration of AI, computer vision and
  interaction design.
- Preview the three modes: terminal, Pygame GUI and physical AR assistant.
- Say the talk shows both the result and the technical evolution.

### 2. The real challenge is keeping four worlds consistent

**Claim:** the problem is not only choosing a move, but connecting reality,
perception, rules and feedback without losing reliability.

**Visual:** four-block flow with the main risks: perspective, lighting,
latency and tactical credibility.

**Speaker notes:**
- Digital Connect Four is easy to represent; the physical world adds noise.
- One inconsistency between colors, player IDs or coordinates produces a
  wrong move.
- Modularity comes from the need to isolate and verify every step.

### 3. From prototype to verified product

**Claim:** the project grew from a monolithic demo into an installable,
diagnosable and measured package.

**Visual:** timeline from December 2025 to October 2026.

**Speaker notes:**
- December: first prototype with PPO, webcam and voice; then physical mode,
  calibration and experiment notebooks.
- May: package refactor, minimax, safety net, watchdog, vision tests and CI.
- September: bitboard engines, board-state validation, exact solver.
- October: opening book and exact oracle (perfect play), automatic board
  localization and lighting adaptation, solver-taught neural network.

### 4. One engine, three experiences, five levels

**Claim:** the same core supports different modes and difficulties without
duplicating logic.

**Visual:** three mockups for CLI, GUI and AR; a difficulty bar.

**Speaker notes:**
- CLI for quick debugging, GUI for the digital experience, AR for the
  physical demo.
- easy, medium, hard, impossible and neural share the same Agent contract.
- The difficulty registry keeps extensions local and reusable.

### 5. Perception, state, decision, interaction

**Claim:** the architecture separates offline data generation and training
from the runtime pipeline, and connects them through the same 6x7 matrix.

**Visual:** two-lane architecture: physical runtime and offline lane
(native solver -> opening book / oracle / teacher data -> distilled CNN).

**Speaker notes:**
- OpenCV produces a discrete grid; models never see camera images.
- rules.py and Connect4Env define what the state means.
- The book, the oracle and the network are all generated offline and
  shipped as files.

### 6. The 6x7 matrix is the shared contract

**Claim:** rules, tests, agents and vision communicate through one minimal,
verifiable representation.

**Visual:** numeric board with a state-action-reward diagram.

**Speaker notes:**
- State: NumPy int8 array with values 0, 1 and 2.
- Action: a column from 0 to 6; gravity decides the row.
- Rewards: +1 win, 0 transition/draw, -10 illegal move; the training wrapper
  turns an opponent win into -1.

### 7. Perfect play needs an opening book

**Claim:** pure-Python search cannot prove the opening in time, so the
answers are computed once, offline, and looked up.

**Visual:** a game tree where the AI's moves are fixed and only the
opponent branches, ending at ply 17; the size: 533k positions in 950 KiB.

**Speaker notes:**
- Measured: with 3 s, only 4-56% of positions at plies 8-13 could be proven.
- A native solver (Pascal Pons) computes the strongly optimal move for every
  position the AI can reach up to ply 17, for both colors.
- After the book the Python solver proves every move; interleaved root
  proofs keep it under the 3 s budget.

### 8. "Perfect" is measured, not claimed

**Claim:** an exact oracle grades every move of every tier.

**Visual:** bar chart of value-preserving moves per tier on game lines:
impossible 100%, neural 96.3%, hard 90.8%, medium 77.5%, easy 65.6%.

**Speaker notes:**
- 729 positions with the exact score of every column.
- Value-preserving: a won game stays won, a drawn one stays drawn.
- Beating weak opponents proves little; the oracle shows where each engine
  goes wrong.

### 9. The network learns from the solver

**Claim:** distilling exact labels turned the weakest tier into a strong
one, and the learning story is the lesson.

**Visual:** before/after: PPO against a random opponent (59.7%) vs CNN
distilled from solver labels (96.3% value-preserving on game lines).

**Speaker notes:**
- The old policy only ever played first, against random moves.
- The new one: a small CNN over self/opponent/empty planes, trained on
  ~308k solver-labelled positions (and their mirror images).
- It plays from its own judgment, without search or safety net.

### 10. The board finds itself

**Claim:** the lattice of holes turns a tilted camera view into a measurable
grid - no clicks needed.

**Visual:** tilted camera, detected holes, fitted 6x7 lattice, homography,
rectified 700x600 board.

**Speaker notes:**
- The holes are the non-blue blobs inside the blue frame; the four corner
  holes define the lattice.
- The lattice must predict the detected holes, otherwise the user clicks
  four corners (any order).
- The warp makes the 42 cells regular and comparable.

### 11. Every cell becomes a color measurement that adapts

**Claim:** HSV bands, inset ROIs and explicit thresholds keep recognition
easy to explain - and every validated reading re-fits it to the light.

**Visual:** 6x7 board, zoom on one cell, HSV bands moving between bright and
dim light, fill-ratio bar.

**Speaker notes:**
- Red needs two hue ranges because it wraps around 0/180; yellow one.
- The ROI drops 20% of the borders; a cell is occupied when 30% of its
  pixels match a color.
- New thresholds are adopted only if they reproduce the validated reading
  exactly.

### 12. From frame to AR arrow

**Claim:** a physical move passes through controlled, validated
transformations before it returns to the user.

**Visual:** webcam -> grid -> validation -> swap -> agent -> mirror ->
overlay/voice.

**Speaker notes:**
- The validator rejects impossible readings (a hand, a token mid-drop).
- Vision uses 1=red and 2=yellow; agents use 1=self and 2=opponent;
  swap_perspective translates.
- The feed is mirrored, so the spoken column is translated to the physical
  board.

### 13. Reliability is a feature

**Claim:** tests, CI, the oracle, the watchdog and fail-soft components turn
observed bugs into automated regressions.

**Visual:** quality metrics and three problem -> fix -> proof cases.

**Speaker notes:**
- 273 headless tests: no webcam, audio or trained model required; CLI,
  GUI and AR loops are tested end to end.
- CI on Python 3.10-3.13 plus Windows and macOS, with Ruff, Mypy, a coverage
  floor and a wheel smoke test.
- Examples: an ignored threat (safety net + watchdog), a starved winning
  proof (interleaved search), dim light (self-checking color adaptation).

### 14. The next step starts from real limits

**Claim:** Pefforza already plays perfectly; the roadmap is about the real
world.

**Visual:** four-step roadmap and a final takeaway.

**Speaker notes:**
- Real webcam photos as regression fixtures; automatic re-localization when
  the camera moves.
- Off-book coverage for games joined midway; fastest wins past the book.
- Perfect play in the browser demo; ONNX export of the network.
- Closing: the main value is verifiable integration, not a single
  algorithm.
