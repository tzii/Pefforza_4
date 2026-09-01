# Contributing

Thanks for your interest in Pefforza. Quick guide so your changes land smoothly.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows
source .venv/bin/activate      # macOS / Linux
pip install -e ".[dev]"
```

## Workflow

1. Branch from `main`.
2. Make your change in small, logical commits.
3. Run the quality gate locally:

   ```bash
   python -m ruff check .
   python -m ruff format --check .
   python -m pytest --cov=pefforza
   ```

4. Open a pull request. CI runs the same checks on Python 3.10–3.13.

## Style

- Code follows `ruff` defaults plus the rules listed in `pyproject.toml`.
- Public API additions deserve a short docstring and a test.
- Keep changes minimal and focused — see `AGENTS.md` for the full conventions.

## Reporting issues

Open a GitHub issue with:

- what you expected
- what happened (logs / stack trace help)
- OS, Python version, and how you installed dependencies
