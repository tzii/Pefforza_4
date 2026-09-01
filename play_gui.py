"""Backwards-compatible shim: the implementation lives in ``pefforza.cli.play_gui``.

The installed console command is ``pefforza-gui``; this file only keeps
``python play_gui.py`` working from a source checkout.
"""

from __future__ import annotations

import sys

from pefforza.cli.play_gui import main

if __name__ == "__main__":
    sys.exit(main())
