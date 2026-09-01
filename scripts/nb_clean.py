"""Strip outputs and execution counts from Jupyter notebooks in-place.

Lightweight, no extra dependency (avoids pulling ``nbstripout`` for a
single-purpose helper). Mirrors what ``nbstripout`` does for the common case.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def strip_notebook(path: Path) -> bool:
    """Strip outputs / execution_count from a notebook. Returns True if changed."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"skip {path}: {exc}", file=sys.stderr)
        return False

    changed = False
    for cell in data.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        if cell.get("outputs"):
            cell["outputs"] = []
            changed = True
        if cell.get("execution_count") is not None:
            cell["execution_count"] = None
            changed = True

    if changed:
        path.write_text(
            json.dumps(data, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return changed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "paths",
        nargs="*",
        help="Notebook files or directories to clean. Required.",
    )
    args = p.parse_args(argv)
    if not args.paths:
        p.error("Pass at least one notebook or directory.")

    targets: list[Path] = []
    for raw in args.paths:
        path = Path(raw)
        if path.is_dir():
            targets.extend(sorted(path.rglob("*.ipynb")))
        elif path.suffix == ".ipynb":
            targets.append(path)

    any_changed = False
    for nb in targets:
        if strip_notebook(nb):
            print(f"stripped {nb}")
            any_changed = True
    return 0 if any_changed or not targets else 0


if __name__ == "__main__":
    raise SystemExit(main())
