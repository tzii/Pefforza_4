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
   python -m mypy
   python -m pytest --cov=pefforza
   ```

   Coverage must stay at or above `fail_under` in `pyproject.toml`; raise
   that floor when you improve coverage, never lower it.

4. Add a line under `## [Unreleased]` in `CHANGELOG.md` for user-visible
   changes.
5. Open a pull request. CI runs the same checks on Python 3.10–3.13
   (Ubuntu) and on Windows and macOS.

## Style

- Code follows `ruff` defaults plus the rules listed in `pyproject.toml`.
- Public API additions deserve a short docstring and a test.
- Keep changes minimal and focused — see `AGENTS.md` for the full conventions.

## Regenerating bundled data

The opening book, the oracle set and the neural-tier teacher data are built
offline with Pascal Pons' native solver (AGPL-3.0, like this project); the
build instructions are in `scripts/native_solver.py`. All three scripts are
seeded and deterministic:

```bash
python scripts/build_opening_book.py --solver path/to/c4solver --max-ply 17
python scripts/build_oracle_set.py   --solver path/to/c4solver
python scripts/build_teacher_set.py  --solver path/to/c4solver --games 30000 --out teacher.npz
python -m pefforza.agent.train --teacher teacher.npz --epochs 12     --out pefforza/agent/models/notebook_model.zip
```

After regenerating, re-run `python -m pefforza.agent.evaluate --oracle
--difficulty impossible` (and `neural`) and update the README numbers.

## Releasing

1. Move the `## [Unreleased]` entries into a new `## [X.Y.Z] - YYYY-MM-DD`
   section of `CHANGELOG.md` and set `version = "X.Y.Z"` in `pyproject.toml`.
2. Merge to `main`, then tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. The `Release` workflow checks that the tag, the version and the changelog
   agree, builds and verifies the distributions, publishes to PyPI through
   Trusted Publishing, and creates the GitHub release from the changelog
   section. (One-time PyPI setup: add a trusted publisher for workflow
   `release.yml`, environment `pypi`.)

## Reporting issues

Open a GitHub issue with:

- what you expected
- what happened (logs / stack trace help)
- OS, Python version, and how you installed dependencies
