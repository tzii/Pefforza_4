"""Physical-plausibility validation for webcam-detected boards.

A single HSV classification of one frame is noisy: a hand over the board can
hide a token, a token photographed mid-drop floats above an empty cell, and
glare can flip a cell's color. Feeding any of those straight into the AI
produces confident nonsense.

:class:`BoardStateValidator` is the minimal gate from the technical plan
(8.2): before a detected grid can drive an AI recommendation it must be

* structurally plausible - gravity holds, no token floats over an empty cell;
* turn-compatible - token counts match the red-first move order;
* outcome-compatible - a connect four is only present with the exact token
  counts of a game that just ended, and never for both colors at once;
* temporally plausible - a valid transition from the last accepted state adds
  a single legal drop or one full legal round (two alternating drops, e.g.
  when the board is analyzed once per round instead of once per move), and
  never removes or recolors a token;
* terminal-aware - once a win is accepted, no further moves are accepted
  (clearing the board starts a new game instead).

The controller combines the validator with :func:`pefforza.rules.player_to_move`
so the AI is only consulted on its own turn.

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
        if not bool(np.isin(grid, (0, 1, 2)).all()):
            return Validation(False, "unsupported token value: cells must be 0, 1, or 2")

        if self._last_was_terminal and self._last_accepted is not None:
            if not grid.any():
                # An empty reading right after a finished game means the
                # board was cleared: start a new match rather than rejecting.
                self._last_accepted = grid.copy()
                self._last_was_terminal = False
                return Validation(True, "board cleared after game over: new game")
            if not np.array_equal(grid, self._last_accepted):
                # Once the game is over, any changed board is stale input -
                # report that before any other diagnosis.
                return Validation(False, "game is over: no further moves are accepted")
            return Validation(True)  # unchanged re-read of the final position

        if not self._structure_ok(grid):
            return Validation(False, "gravity violation: a token floats above an empty cell")
        red = int(np.count_nonzero(grid == 1))
        yellow = int(np.count_nonzero(grid == 2))
        if not self._counts_ok(red, yellow):
            return Validation(False, "token counts are incompatible with the move order")

        red_wins, yellow_wins = self._win_colors(grid)
        if red_wins and yellow_wins:
            return Validation(False, "both colors have a connect four at once")
        if (red_wins or yellow_wins) and not self._winner_counts_ok(red_wins, red, yellow):
            return Validation(
                False, "a connect four is present but the token counts say play continued"
            )

        if self._last_accepted is not None:
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

    def _counts_ok(self, red: int, yellow: int) -> bool:
        if self.red_moves_first:
            return yellow <= red <= yellow + 1
        return red <= yellow <= red + 1

    @staticmethod
    def _win_colors(grid: Grid) -> tuple[bool, bool]:
        """Detect red/yellow connect-fours independently of each other."""
        red_only = grid.copy()
        red_only[grid == 2] = 0
        yellow_only = grid.copy()
        yellow_only[grid == 1] = 0
        return check_winner(red_only) == 1, check_winner(yellow_only) == 2

    def _winner_counts_ok(self, red_wins: bool, red: int, yellow: int) -> bool:
        """A connect four ends the game on the winner's own move, so the counts
        must be exactly the end-of-game ones: the first mover ends one ahead,
        the second mover ends level."""
        if self.red_moves_first:
            return (red == yellow + 1) if red_wins else (red == yellow)
        return (red == yellow) if red_wins else (yellow == red + 1)

    @staticmethod
    def _check_transition(prev: Grid, curr: Grid) -> Validation:
        removed = (prev != 0) & (curr == 0)
        recolored = (prev != 0) & (curr != 0) & (prev != curr)
        added = (prev == 0) & (curr != 0)

        if removed.any():
            return Validation(False, "a token disappeared between reads")
        if recolored.any():
            return Validation(False, "a token changed color between reads")

        cells = [(int(r), int(c)) for r, c in zip(*added.nonzero(), strict=True)]
        if not cells:
            return Validation(True)  # unchanged board, re-read
        if len(cells) == 1:
            row, col = cells[0]
            # The new token must be a legal drop: resting on the floor or exactly
            # on top of the previous stack in that column.
            if row != ROWS - 1 and prev[row + 1, col] == 0:
                return Validation(False, "the new token appeared mid-air, not on the stack")
            return Validation(True)
        if len(cells) == 2:
            return BoardStateValidator._check_round_transition(prev, curr, cells)
        return Validation(
            False,
            "more than two tokens appeared between reads "
            "(press SPACE after each move, or 'r' to resync)",
        )

    @staticmethod
    def _check_round_transition(prev: Grid, curr: Grid, cells: list[tuple[int, int]]) -> Validation:
        """Accept a full-round read: two alternating drops between analyses.

        The natural physical workflow analyzes once per *round* - the AI's
        move and the human reply both land between two reads. Such a read is
        legal iff replaying the two drops in turn order keeps every
        intermediate position playable: the first token must rest on the
        previous stack, must not complete a win (the game would be over), and
        the second token must rest on the resulting stack.
        """
        (r1, c1), (r2, c2) = cells
        color1 = int(curr[r1, c1])
        color2 = int(curr[r2, c2])
        if color1 == color2:
            return Validation(False, "the two new tokens do not alternate colors")

        # Order the drops by turn: whose move was due on prev decides who went
        # first; in a shared column the lower drop must also be the earlier one.
        prev_red = int(np.count_nonzero(prev == 1))
        first_color = 1 if prev_red == int(np.count_nonzero(prev == 2)) else 2
        if color1 != first_color:
            (r1, c1, color1), (r2, c2, color2) = (r2, c2, color2), (r1, c1, color1)
        if c1 == c2 and r1 < r2:
            return Validation(False, "two new tokens in one column do not stack in turn order")

        if r1 != ROWS - 1 and prev[r1 + 1, c1] == 0:
            return Validation(False, "the round's first token appeared mid-air")
        mid = prev.copy()
        mid[r1, c1] = color1
        if check_winner(mid) != 0:
            # The first move ended the game; the reply must not exist.
            return Validation(False, "play continued after a connect four mid-round")
        if r2 != ROWS - 1 and mid[r2 + 1, c2] == 0:
            return Validation(False, "the round's second token appeared mid-air")
        return Validation(True)


__all__ = ["BoardStateValidator", "Grid", "Validation"]
