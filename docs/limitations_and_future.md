# Performance, Limitations, Future Work and Glossary

> 🇮🇹 [Versione italiana](it/limitations_and_future.md)

This module summarizes the performance work in Pefforza, its current
limits, the improvement roadmap, and a glossary of project terms.

---

## 1. Performance and scalability

1. **Bitboards**: `BitPosition` stores a position as two integers (seven bits
   per column, one sentinel bit). Wins, threats and legal moves are a few
   shifts and masks instead of array scans, which makes the `hard` tier an
   order of magnitude faster than the matrix baseline it is pinned to.
2. **Opening book lookup**: the book is a sorted array of 533k canonical keys
   (950 KiB compressed, loaded once); a lookup is one binary search, so the
   first 17 plies are answered in well under a millisecond.
3. **Interleaved root proofs**: past the book, `solve_root` gives every
   unresolved root move a geometrically growing node allowance, so a cheap
   winning proof is not starved behind expensive refutations. On the
   oracle's game lines the slowest proof dropped from 9.5 s to under 3 s.
4. **Symmetry-canonical transposition table**: a position and its mirror
   share one fixed-size table entry, packed into parallel integer arrays.
5. **Cached board surface in Pygame**: the static board is pre-rendered
   once per settled move; drop animations only blit that surface plus one
   circle per frame, which removes flicker.
6. **Center-first move ordering**: searches try `[3, 2, 4, 1, 5, 0, 6]` (then
   by winning spots), so alpha-beta cuts the worst branches early.

---

## 2. Known limitations

1. **Off-book positions**: the book covers every position the `impossible`
   AI can reach *when it plays from the first move*. If it joins a game in
   progress (e.g. a physical board where someone else played the opening),
   shallow positions may be unprovable within the budget and the move is
   the tactically-safe fallback - 97-98% value-preserving on the oracle's
   off-book positions rather than 100%.
2. **Fastest win past the book**: the solver past ply 17 is weak (win /
   draw / loss), so it always keeps a won game won but does not always pick
   the quickest win (about 73% exactly optimal there).
3. **Vision is tested on rendered scenes**: localization and lighting
   adaptation are verified on synthetic boards under perspective, clutter
   and dim light, but the repository has no real webcam photos yet (the
   test suite picks them up automatically once added to
   `tests/fixtures/vision/`).
4. **Localization assumptions**: automatic calibration expects a blue frame
   with at least ~85% of its holes visible; heavy occlusion or an unusual
   board color needs the manual four-click calibration.
5. **Camera or board movement**: the perspective matrix is fixed after
   calibration; if the camera or board moves, restart the assistant to
   recalibrate.
6. **Neural tier is an imitation**: the CNN is distilled from exact solver
   labels and is far stronger than the old PPO policy, but it is not perfect
   (see the README for its oracle score) and is deliberately not wrapped by
   the tactical safety net, so it shows what the network itself learned.
7. **Model start-up**: importing Stable-Baselines3/PyTorch for the `neural`
   tier adds about 1-2 s at start.

---

## 3. Roadmap

| Priority | Improvement | Why | Files | Risk |
|:---|:---|:---|:---|:---|
| **P1** | **Real webcam fixtures** | Regression-test vision on real lighting, glare and boards, not just rendered scenes. | `tests/fixtures/vision/` | Low |
| **P1** | **Continuous re-localization** | Detect camera/board movement and re-run `locate_board` automatically instead of requiring a restart. | `board_detector.py`, `play_physical.py` | Medium |
| **P2** | **Off-book coverage** | Add all positions up to ~ply 8 to the book so joining a game in progress is also perfect. | `scripts/build_opening_book.py`, `book.py` | Low |
| **P2** | **Strong solving past the book** | Prefer the fastest win when it fits the budget. | `search/perfect.py` | Medium |
| **P3** | **Perfect play in the browser** | Port the book lookup and solver to the website demo (TypeScript/WASM). | `website/` | Medium |
| **P3** | **ONNX export** | Run the neural tier without PyTorch. | new export module | Medium |

Done since the previous roadmap: automatic color calibration (lighting
adaptation), automatic board-corner detection, solver-taught neural
training, and perfect opening play.

---

## 4. Glossary

| Term | Meaning | Where |
|:---|:---|:---|
| **Bitboard** | A position encoded as integers, one bit per cell, so game rules become bit operations. | `agent/search/bitboard.py` |
| **Opening book** | A precomputed table of perfect moves for early positions, generated offline by a native solver. | `agent/search/book.py` |
| **Oracle** | Positions with the exact score of every column, used to grade agents move by move. | `agent/oracle.py` |
| **Value-preserving move** | A move that keeps the game-theoretic outcome (won stays won, drawn stays drawn). | `agent/oracle.py` |
| **Exactly optimal move** | A value-preserving move that also wins fastest or loses slowest. | `agent/oracle.py` |
| **Weak / strong solving** | Computing only win/draw/loss vs. the exact distance to the end of the game. | `agent/search/perfect.py` |
| **Transposition table** | A cache of search results keyed by position, shared between move orders that reach the same position. | `agent/search/perfect.py` |
| **Negamax** | Minimax for zero-sum games using max(a, b) = -min(-a, -b). | `agent/minimax.py`, `agent/search/` |
| **Tactical safety net** | Deterministic 1-ply guard: take an immediate win, else block an immediate threat. | `agent/minimax.py` |
| **Distillation** | Training a network to imitate a stronger teacher (here, the exact solver's labels). | `agent/train.py` |
| **PPO** | Proximal Policy Optimization, the reinforcement learning algorithm used for fine-tuning. | `agent/train.py` |
| **Gymnasium** | The maintained successor of OpenAI Gym, the standard RL environment API. | `envs/connect4_env.py` |
| **Perspective warp / homography** | A 3 x 3 transform that maps the tilted camera view of the board to a front-on rectangle. | `vision/board_detector.py` |
| **Hole lattice** | The 6 x 7 grid of hole centers used to locate the board automatically. | `vision/board_detector.py` |
