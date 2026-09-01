"""Physical-plausibility validation for webcam-detected boards.

A single HSV classification of one frame is noisy: a hand over the board can
hide a token, a token photographed mid-drop floats above an empty cell, and
glare can flip a cell's color. Feeding any of those straight into the AI
produces confident nonsense.

:class:`BoardStateValidator` is the minimal gate from the technical plan
(8.2): before a detected grid can drive an AI recommendation it must be

* structurally plausible - gravity holds, no token floats over an empty cell;
* turn-compatible - token counts match the red-first move order;
* temporally plausible - a valid transition from the last accepted state adds
  at most one legally dropped token and never removes or recolors one;
* terminal-aware - once a win is accepted, no further moves are accepted
  (clearing the board starts a new game instead).

Pure NumPy logic on the vision grid (``1 = red, 2 = yellow``); no camera,
display, or model required, so it is fully unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from pefforza.constants import COLS, ROWS
from pefforza.rules import check_winner

Grid = NDArray[np.int8]


@dataclass(frozen=True)
class Validation:
    """Outcome of :meth:`BoardStateValidator.accept`.

    ``reason`` is a human-readable explanation; it is set for rejections and
    for informational accepts (e.g. new-game detection).
    """

    ok: bool
    reason: str | None = None

    def __bool__(self) -> bool:
        return self.ok


class BoardStateValidator:
    """Accepts only physically and temporally plausible board states."""

    def __init__(self, *, red_moves_first: bool = True) -> None:
        self.red_moves_first = red_moves_first
        self._last_accepted: Grid | None = None
        self._last_was_terminal = False

    @property
    def last_accepted(self) -> Grid | None:
        """The most recently accepted grid (a copy), or None if none yet."""
        return None if self._last_accepted is None else self._last_accepted.copy()

    def reset(self) -> None:
        """Forget all history (used when re-calibrating or starting over)."""
        self._last_accepted = None
        self._last_was_terminal = False

    def accept(self, grid: Grid) -> Validation:
        """Try to accept ``grid`` as the new trusted state of the board."""
        grid = np.asarray(grid)
        if grid.shape != (ROWS, COLS):
            return Validation(False, f"expected a {ROWS}x{COLS} grid, got {grid.shape}")

        if self._last_was_terminal and not grid.any():
            # An empty reading right after a finished game means the board
            # was cleared: start a new match rather than rejecting forever.
            self._last_accepted = grid.copy()
            self._last_was_terminal = False
            return Validation(True, "board cleared after game over: new game")

        if not self._structure_ok(grid):
            return Validation(False, "gravity violation: a token floats above an empty cell")
        if not self._counts_ok(grid):
            return Validation(False, "token counts are incompatible with the move order")

        if self._last_accepted is not None:
            if self._last_was_terminal:
                return Validation(False, "game is over: no further moves are accepted")
            transition = self._check_transition(self._last_accepted, grid)
            if not transition.ok:
                return transition

        self._last_accepted = grid.copy()
        self._last_was_terminal = check_winner(grid) != 0
        return Validation(True)

    # ------------------------------------------------------------- internals
    @staticmethod
    def _structure_ok(grid: Grid) -> bool:
        """Gravity: an occupied cell may never sit directly above an empty one."""
        return not bool(((grid[:-1] != 0) & (grid[1:] == 0)).any())

    def _counts_ok(self, grid: Grid) -> bool:
        red = int(np.count_nonzero(grid == 1))
        yellow = int(np.count_nonzero(grid == 2))
        if self.red_moves_first:
            return yellow <= red <= yellow + 1
        return red <= yellow <= red + 1

    @staticmethod
    def _check_transition(prev: Grid, curr: Grid) -> Validation:
        removed = (prev != 0) & (curr == 0)
        recolored = (prev != 0) & (curr != 0) & (prev != curr)
        added = (prev == 0) & (curr != 0)

        if removed.any():
            return Validation(False, "a token disappeared between reads")
        if recolored.any():
            return Validation(False, "a token changed color between reads")

        cells = list(zip(added.nonzero()[0], added.nonzero()[1], strict=True))
        if not cells:
            return Validation(True)  # unchanged board, re-read
        if len(cells) > 1:
            return Validation(False, "more than one token appeared between reads")

        row, col = int(cells[0][0]), int(cells[0][1])
        # The new token must be a legal drop: resting on the floor or exactly
        # on top of the previous stack in that column.
        if row != ROWS - 1 and prev[row + 1, col] == 0:
            return Validation(False, "the new token appeared mid-air, not on the stack")
        return Validation(True)


__all__ = ["BoardStateValidator", "Grid", "Validation"]
