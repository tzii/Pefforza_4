# Desktop release verification

This pass continues `codex/tactical-lessons` from `81689a2`, including the
lessons, Windows fixes, camera scheduling, fallback labels, and browser rendering
changes committed and pushed as
[`9ed3453a9dc485990a54c966cf105a273f22c9e6`](https://github.com/tzii/Pefforza_4/commit/9ed3453a9dc485990a54c966cf105a273f22c9e6).
The results below describe that implementation revision. For later changes,
record the tested full SHA and its matching Actions run.

## Changes checked

- Hints and emergency worker fallbacks take immediate wins, then exclude moves
  allowing an immediate winning reply when another move avoids it. When every
  move allows such a reply, the hint says so. This is not a deeper search proof.
- Regression cases include the one-based sequence `6,5,2,6,7,7,1,5`, mirrored
  boards, both player perspectives, unavoidable losses, and agreement with the
  block/safety lesson answer sets. Lesson answers remain independently enumerated.
- Real spawned workers are cancelled with buffered replies across undo, restart,
  difficulty changes, entering/changing/retrying lessons, returning to free play,
  and closing. Synthetic camera cases cover resync, disconnect, rejected/missing
  reads, new turns, terminal wins, and full draws.
- The distribution check runs outside the checkout with isolated venv Python,
  verifies the imported package and resource locations, loads the real PPO
  checkpoint, performs inference, and finishes a game with the installed search
  worker. An unexpected model-load or worker fallback fails the check.
- Source distributions include the browser preview assets and verification
  scripts needed by their tests. CI runs on branch pushes as well as PRs, with
  Linux Python 3.10–3.13 and Windows Python 3.13 checks, plus Linux/Windows wheel
  checks using Python 3.12.

## Published CI evidence · 8 September 2026

[Actions run 34174853077](https://github.com/tzii/Pefforza_4/actions/runs/34174853077)
completed successfully for
`9ed3453a9dc485990a54c966cf105a273f22c9e6`. All seven jobs passed:

| Checks | Platforms | Result |
| :--- | :--- | :--- |
| Ruff lint/format, Mypy, browser motion tests, Pytest | Linux Python 3.10, 3.11, 3.12, 3.13; Windows Python 3.13 | 506 tests passed and 89% package coverage in each configuration; all other checks passed |
| Build, clean wheel install, dependency check, entrypoints, model and game smoke test | Linux and Windows, Python 3.12 | Both jobs passed |

Both wheel logs confirm imports from the fresh virtual environment's
`site-packages`, no broken dependencies, and all three installed entrypoints'
`--help` checks. The bundled checkpoint loaded and inferred column 4; the
installed Hard search worker finished a 10-move game without fallback on each OS.

The branch is published; it has not been merged as part of this verification.
CI establishes the automated software and distribution results. The remaining
native input, display, camera, and speech checks are listed below and ordered
in [NEXT_STEPS.md](NEXT_STEPS.md).

## Reproduce

From an activated development environment at the revision being checked:

```text
python -m ruff check .
python -m ruff format --check .
python -m mypy
node --test tests/test_preview_motion.mjs
python -m pytest --cov=pefforza --cov-report=term-missing
python -m build
```

Set `PEFFORZA_TTS_BACKEND=null` for tests. Build tooling (`build`) and Node.js
are development tools, not game runtime dependencies. The workflow in
`.github/workflows/ci.yml` installs the wheel into a fresh virtual environment,
checks dependencies and all three console entrypoints, then executes:

```text
<wheel-venv-python> -I <absolute-checkout-path>/scripts/smoke_wheel.py
```

Run that last command from a temporary directory outside the checkout. An
editable install is not a substitute for the wheel check.

## Local results and exclusions

On 8 September 2026, Windows / Python 3.13.15 passed **506 tests with 89%
package coverage**, Ruff lint/format, Mypy (28 source files), and all three
browser motion tests. The full suite was run with null TTS outside the restricted
process sandbox after sandbox runs delayed some test workers past the watchdog.
The test helper waits beyond the application watchdog; the production timeout
and assertions about illegal results remain unchanged.

The successful pytest command used `--cov=pefforza --cov-report=term-missing`,
an external `--basetemp`, `-o cache_dir=...`, and `COVERAGE_FILE` in a fresh
temporary directory to avoid inherited cache permissions. Ruff and Mypy likewise
used writable caches. These settings change artifact locations, not test selection.

The clean wheel environment passed `pip check` and all three entrypoints'
`--help` commands. Isolated verification imported `pefforza` from that venv's
`site-packages`, loaded the actual bundled checkpoint (predicting column 4 on
the empty board), and finished a 10-move game with the Hard worker without a
fallback. This used SB3 2.9.0, PyTorch 2.14.0, and NumPy 2.5.3, resolved from
the declared dependencies rather than the existing development environment.

Native mouse walkthrough on 8 September 2026 passed: a move and Hard reply,
Undo, Hint, horizontal and vertical lesson completion, Next lesson, return to
free play, and closing. The default 1040-by-820 canvas and a maximized window
were inspected; column hit mapping worked after maximizing. Smaller laptop
windows and other display scaling settings still need a manual readability pass.
Keyboard event tests pass, but native keystroke injection did not register in
this automation session, so a manual keyboard check remains pending.

Webcam calibration, real-board recognition, and audible speech require separate
hardware acceptance. Synthetic inputs do not certify those capabilities.
Browser screenshots do not certify the native Pygame layout. Exact-engine
strength, dependency splitting, and move review/retry remain future work.
