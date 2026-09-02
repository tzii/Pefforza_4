"""Pefforza: Connect 4 AI with vision, voice, and an RL agent."""

from importlib.metadata import PackageNotFoundError, version

# Single source of truth: the version lives in pyproject.toml and is read
# from the installed package metadata. A source checkout without an install
# falls back to a clearly-invalid sentinel instead of drifting out of sync.
try:
    __version__ = version("pefforza")
except PackageNotFoundError:  # pragma: no cover - uninstalled source tree
    __version__ = "0.0.0.dev0"

# Public, stable surface used across entrypoints and tests.
from pefforza.constants import (
    AI_PLAYER,
    COLS,
    DEFAULT_MODEL_PATH,
    EMPTY,
    HUMAN_PLAYER,
    ROWS,
)
from pefforza.rules import (
    available_columns,
    check_winner,
    is_board_full,
    swap_perspective,
)

__all__ = [
    "__version__",
    "AI_PLAYER",
    "COLS",
    "DEFAULT_MODEL_PATH",
    "EMPTY",
    "HUMAN_PLAYER",
    "ROWS",
    "available_columns",
    "check_winner",
    "is_board_full",
    "swap_perspective",
]
