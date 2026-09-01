"""Backwards-compatible shim: the implementation lives in ``pefforza.cli.play_cli``.

The installed console command is ``pefforza-cli``; this file only keeps
``python play_cli.py`` working from a source checkout.
"""

from __future__ import annotations

import sys

from pefforza.cli.play_cli import main

if __name__ == "__main__":
    sys.exit(main())
