"""Backwards-compatible shim for the continuously-watching AR assistant.

Equivalent to ``pefforza-physical --watch --voice --ai-color yellow``; any
extra arguments are forwarded and win over these defaults (for example
``python main.py --no-voice --difficulty impossible``).
"""

from __future__ import annotations

import sys

from pefforza.cli.play_physical import main

WATCH_DEFAULTS = ["--watch", "--voice", "--ai-color", "yellow"]

if __name__ == "__main__":
    sys.exit(main([*WATCH_DEFAULTS, *sys.argv[1:]]))
