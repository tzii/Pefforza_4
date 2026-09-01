"""Pefforza: Connect 4 AI with vision, voice, and an RL agent."""

__version__ = "0.2.0"

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
