# Contributing

Thanks for your interest in Pefforza. Quick guide so your changes land smoothly.

## Setup

Follow the [README quick start](README.md#quick-start) for your operating
system, then install the development tools in that activated environment:

```bash
python -m pip install -e ".[dev]"
```

## Workflow

1. Branch from `main`.
2. Make your change in small, logical commits.
3. Run the quality gate locally:

   ```bash
   python -m ruff check .
   python -m ruff format --check .
   python -m mypy
   python -m pytest --cov=pefforza
   ```

4. Open a pull request. CI runs the same checks on Python 3.10–3.13.

For desktop changes, exercise a move and AI reply, undo while thinking, hints,
replay after a result, resized input, and quitting. `python scripts/preview_gui.py`
runs the real renderer in a local browser remote when no native display is
available. Capture fresh screenshots; do not present mockups as running UI.
Camera/audio changes need synthetic regression tests plus clearly stated
hardware verification limits. See the [audit checklist](docs/PROJECT_STATUS.md).

## Style

- Code follows `ruff` defaults plus the rules listed in `pyproject.toml`.
- Public API additions deserve a short docstring and a test.
- Keep changes minimal and focused — see `AGENTS.md` for the full conventions.

## Reporting issues

Open a GitHub issue with:

- what you expected
- what happened (logs / stack trace help)
- OS, Python version, and how you installed dependencies
