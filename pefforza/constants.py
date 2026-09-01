"""Shared constants. Single source of truth for board geometry and conventions.

Player IDs:
    0 = empty cell
    1 = first player (in the env, this is the agent's perspective)
    2 = second player (opponent from the agent's perspective)

In the *vision* pipeline the convention is:
    1 = Red token, 2 = Yellow token.
Whether the AI plays Red or Yellow is decided at runtime by the entrypoint;
use ``rules.swap_perspective`` to translate between vision and model views.
"""

from __future__ import annotations

from pathlib import Path

ROWS: int = 6
COLS: int = 7
WIN_LENGTH: int = 4

EMPTY: int = 0
AI_PLAYER: int = 1
HUMAN_PLAYER: int = 2

# Resolved relative to the package install location so it works regardless of
# the current working directory.
_PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH: Path = _PACKAGE_DIR / "agent" / "models" / "notebook_model.zip"
