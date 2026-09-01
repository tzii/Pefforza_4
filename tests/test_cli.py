"""Smoke tests for the console entrypoints under ``pefforza.cli``.

The ``[project.scripts]`` console scripts point at ``pefforza.cli.*``; these
tests pin that contract so a packaging regression (missing module, broken
import, camera/audio initialization at import time) fails CI instead of the
user's first invocation. No webcam, audio device, or trained model is needed:
``--help`` exits during argument parsing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        cwd=REPO_ROOT,
    )


def test_entrypoint_modules_expose_main():
    from pefforza.cli import play_cli, play_gui, play_physical

    for module in (play_cli, play_gui, play_physical):
        assert callable(module.main)


def test_play_cli_help_smoke():
    result = _run([sys.executable, "-m", "pefforza.cli.play_cli", "--help"])
    assert result.returncode == 0, result.stderr


def test_play_gui_help_smoke():
    result = _run([sys.executable, "-m", "pefforza.cli.play_gui", "--help"])
    assert result.returncode == 0, result.stderr


def test_play_physical_help_smoke():
    result = _run([sys.executable, "-m", "pefforza.cli.play_physical", "--help"])
    assert result.returncode == 0, result.stderr


def test_root_shims_still_work():
    """The repo-root ``play_*.py`` files must keep ``python play_cli.py`` alive."""
    result = _run([sys.executable, "play_cli.py", "--help"])
    assert result.returncode == 0, result.stderr
