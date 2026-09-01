# AGENTS.md — guidance for AI / automation agents working on Pefforza

This file is the source of truth for any automated assistant editing this
repository. Keep edits small, justified, and runnable.

## Project at a glance

- **Stack**: Python 3.10–3.13, Gymnasium, Stable-Baselines3, OpenCV, Pygame, pyttsx3.
- **Layout**: installable package `pefforza/` with `agent/`, `envs/`, `vision/`, `interaction/`, `cli/`, plus pure-logic modules `constants.py` and `rules.py`. Entrypoint implementations live in `pefforza/cli/` (`play_cli`, `play_gui`, `play_physical`, exposed as `pefforza-cli` / `pefforza-gui`); the repo-root `play_*.py` files are thin compatibility shims and `main.py` is a continuously-watching AR variant.
- **Tests**: `tests/` with `pytest`. Currently covers `rules` and `Connect4Env`.

## Setup commands

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows (cmd / PowerShell)
source .venv/bin/activate      # macOS / Linux
pip install -e ".[dev]"
```

## Required quality gates

Run these before declaring a task done. CI runs the same set.

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest --cov=pefforza
```

Useful subsets:

```bash
python -m pytest tests/test_rules.py -q
python -m pytest tests/test_connect4_env.py -q
```

## Conventions

- **Single source of truth** for board geometry and player IDs lives in `pefforza/constants.py`. Don't redeclare `ROWS`, `COLS`, `WIN_LENGTH`, or model paths elsewhere.
- **Pure game logic** (`check_winner`, `swap_perspective`, etc.) lives in `pefforza/rules.py`. Reuse it from entrypoints and the env.
- **Player ID convention**:
  - Env / model: `1 = self/agent perspective`, `2 = opponent`.
  - Vision: `1 = red token`, `2 = yellow token`.
  - Translate between them with `swap_perspective`.
- **Imports**: do not add `sys.path.append(...)` hacks. The package is installable; run scripts from the repo root after `pip install -e .`.
- **Logging over print** in long-running scripts; `print` is fine in CLI prompts and notebooks.
- **Voice**: `VoiceEngine` must remain fail-soft. Never let TTS errors crash the game.

## Adding a feature

1. Decide whether new logic belongs in `rules.py` (pure), the env, the vision module, or an entrypoint.
2. Add or update tests in `tests/`. Tests must not require a webcam, audio device, or trained model.
3. Run the full quality gate. Fix every failure rather than skipping or `xfail`-ing it.
4. Update `README.md` if you change the public command surface.

## Risk awareness

- `play_*` and `main.py` open a camera and may show OS-level windows. They are not testable in CI by design.
- `pefforza/agent/models/notebook_model.zip` is a trained checkpoint kept in-tree for convenience. Don't commit additional `.zip` checkpoints — `.gitignore` already excludes new ones.
- `.kilo/worktrees/` is an agent-tooling worktree. It is `.gitignore`d going forward; do not edit files inside it.

## Things to avoid

- Bare `except:` — catch the specific exception or `Exception`, and log.
- Reformatting unrelated files. Use `ruff format` only on files you touched.
- Adding new runtime dependencies without updating both `pyproject.toml` and `requirements.txt`, with version bounds.
- Introducing breaking public-API changes without noting them in the PR description.
