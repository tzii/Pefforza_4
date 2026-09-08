# Project audit · September 2026

## What makes this project worth building

Pefforza's strength is the connection between three ways of learning: a game you
can play, an AI whose decisions you can inspect, and a physical board a webcam
can interpret. The improvement strategy is to make that loop trustworthy and
welcoming, rather than add unrelated features or hide uncertainty behind polish.

## Findings and implemented improvements

| Area | Finding in the original code | Improvement and evidence |
| :--- | :--- | :--- |
| Desktop | Search and animation blocked input; results automatically closed the game; no replay or practice controls | Cancellable spawn worker, nonblocking animation, persistent results, undo, explained hints, keyboard play, scalable window. `test_gui.py` and `test_gui_game.py` cover the controller and event flow. |
| Environment | Returned observations shared mutable board memory; steps after termination remained possible; fractional actions were coerced; advertised RGB rendering returned nothing | Independent observations, explicit terminal lifecycle, strict discrete actions, real RGB arrays. `test_connect4_env.py`. |
| Search | Cached mate distances were relative to an old root; deeper heuristic cache entries could alter fixed-depth analysis; malformed boards could silently become bitboards | Position-relative cached mate scores, depth-compatible reuse, terminal and board-input checks. `test_bitboard_search.py`, `test_search_inputs.py`, `test_exact_agent.py`. |
| Training / evaluation | Reset seeds did not reseed the random opponent; training returned a path without the saved `.zip`; malformed model actions and mutable inputs could distort matches | Reproducible reset, real checkpoint path, strict predictions, isolated agent inputs, argument validation, cleanup. `test_train.py`, `test_evaluate.py`, `test_terminal_game.py`. |
| Camera | Corner extrema could select a point twice; failed reads could leave old arrows; the continuous experiment bypassed validation and could suggest full columns | Convex corner validation, stale-recommendation clearing, draw handling, validated and cached continuous recommendations, legal fallback. Synthetic camera and board tests. |
| Voice | Shutdown and late speech could race; backend cleanup or worker-start failure could escape fail-soft handling | Serialized queue shutdown, bounded joins, dropped late speech, cleanup safeguards. `test_voice.py`. |
| Install | SB3's broad `extra` dependency now installs `pygame-ce` alongside the project's `pygame`, sharing an import namespace | Request SB3 core plus the TensorBoard and Matplotlib capabilities actually used. Runtime manifests remain aligned. |
| Documentation | Duplicate installation paths, outdated search attribution, minimal test descriptions, and overconfident AI wording | One user journey, real gameplay imagery, explicit hardware limits, learning experiments, a current documentation index. |

The original test suite passed **248 tests** before the changes. Passing that
suite did not exercise the newly identified edge cases; regression coverage now
targets them explicitly. Run the commands below for the current counts rather
than treating a dated number as a permanent guarantee.

## Reproduce the verification

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy
PEFFORZA_TTS_BACKEND=null python -m pytest --cov=pefforza
python scripts/benchmark_search.py --depths 6 8 --skip-solver
```

The environment-variable prefix above is POSIX shell syntax. In PowerShell, use
`$env:PEFFORZA_TTS_BACKEND = "null"` before the pytest command.

The game controller can be exercised without a native display through
`python scripts/preview_gui.py`: this serves a browser view with vector pieces,
native text, local animation, and a small allowlist of controls. It is a
**development-only**, single-game
remote. Its HTTP server is not a production deployment or security boundary;
keep it on loopback or inside an access-controlled sandbox. No camera footage,
accounts, model uploads, or arbitrary repository files are exposed.

For a hardware sign-off, check camera-open failure, calibration cancellation,
both AI colors, mirrored numbering, a full column, a win, a draw, a rejected
occluded frame, resync, quitting, and speech with/without an available backend.
Synthetic tests cannot substitute for that pass on real devices.

## Compatibility notes

- `Connect4Env.step()` after termination now raises `RuntimeError`: call
  `reset()` first. Returned observations are snapshots, not writable board views.
  Noninteger actions are invalid rather than silently truncated; rewards for
  ordinary legal/illegal moves are unchanged.
- `train()` returns the actual final `.zip` path. Training remains PPO against a
  random opponent, not competitive self-play.
- Search constructors reject malformed/floating boards and replay after a win.
  Exact analysis rejects a won position; a full draw returns no move.
- CLI aliases remain compatible. `pefforza-physical` is now installed alongside
  the terminal and desktop commands. Old GUI drawing helpers were internal
  implementation details and are replaced by `GameView` / `GameApp`.
- The desktop keeps results open rather than exiting after a timer. Changing
  difficulty starts a new round. Undo/restart cancel the AI worker and discard
  its cache and random sequence; saved matches and scores are not implemented.

## The next experiments worth doing

The [software follow-up](NEXT_STEPS.md) now implements six tactical lessons,
cancellable physical-board search, and visible desktop fallback reporting.
Its camera work leaves calibration and token classification unchanged.

| Priority | Experiment | What would count as success |
| :--- | :--- | :--- |
| 1 | **A vision confidence lab**: record consented, cropped board fixtures across lighting conditions, then calibrate HSV thresholds | Report per-cell errors and rejected/incorrect whole-board reads on a held-out set, not only attractive demo footage. |
| 2 | **Extend the tactical lessons**: build on the six checked-in win/block/fork/safety challenges | New puzzles have legal replay sequences and independently checked answers. |
| 3 | **A fair AI report card**: repeatable match seeds, alternating sides, timing and uncertainty | A trained candidate improves across a fixed opponent suite, not just one lucky game. Keep the old model as a baseline. |
| 4 | **Curriculum / historical-policy training** | Beat the random-opponent baseline on held-out opponents without regressing legal-play behavior. |
| 5 | **Stronger exact openings**, via a reviewed native solver or opening database | Measure proof rate, latency, packaging cost, and platform support before changing the default. |

These are proposals, **not shipped features**. In particular, automatic color
calibration, speech recognition, competitive self-play, and native browser AR
are not implemented.

## Research references

The implementation was checked against repository code, installed dependency
metadata, and current primary documentation—not assumptions about old versions:

- [Pygame event queue](https://www.pygame.org/docs/ref/event.html): handle events
  every frame; a blocked event loop can lose input or be marked unresponsive.
- [Gymnasium environment API](https://gymnasium.farama.org/api/env/): reset after
  terminal episodes, typed observations/actions, explicit render modes.
- [Stable-Baselines3 installation](https://stable-baselines3.readthedocs.io/en/master/guide/install.html)
  and [release metadata](https://pypi.org/project/stable-baselines3/): distinguish
  the core library from optional integrations. SB3 2.9.0's `extra` includes
  `pygame-ce`; the project explicitly keeps Pygame 2.6.1 instead of installing both.
- [PyTorch installation](https://pytorch.org/get-started/locally/): CPU wheels
  avoid unnecessary accelerator downloads in development sandboxes.

Local verification used Python 3.12, Gymnasium 1.3.0, SB3 2.9.0 and Pygame 2.6.1.
This is a tested environment, not a lockfile or a claim that every OS/driver
combination has been tested.
