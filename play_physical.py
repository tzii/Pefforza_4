"""Backwards-compatible shim: the implementation lives in ``pefforza.cli.play_physical``.

The module form ``python -m pefforza.cli.play_physical`` is the package
equivalent; this file only keeps ``python play_physical.py`` working from a
source checkout.
"""

from __future__ import annotations

import sys

from pefforza.cli.play_physical import main

if __name__ == "__main__":
    sys.exit(main())
