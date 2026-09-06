"""Compact 49-bit Connect Four position representation.

The 7x6 board uses seven bits per column: six playable cells plus one sentinel
bit. This layout makes move generation and alignment checks cheap integer
operations while keeping the public game/UI representation as a NumPy board.

``BitPosition.current`` always contains the stones of ``to_move``;
``BitPosition.mask`` contains all occupied playable cells. After a move the
perspective is swapped, matching a negamax search naturally.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from operator import index

import numpy as np

from pefforza.constants import COLS, EMPTY, ROWS
from pefforza.rules import Board

STRIDE = ROWS + 1
TOTAL_CELLS = ROWS * COLS

COLUMN_MASKS: tuple[int, ...] = tuple(((1 << ROWS) - 1) << (c * STRIDE) for c in range(COLS))
BOTTOM_MASKS: tuple[int, ...] = tuple(1 << (c * STRIDE) for c in range(COLS))
TOP_MASKS: tuple[int, ...] = tuple(1 << (ROWS - 1 + c * STRIDE) for c in range(COLS))
BOTTOM_MASK = sum(BOTTOM_MASKS)
BOARD_MASK = sum(COLUMN_MASKS)
CENTER_MASK = COLUMN_MASKS[COLS // 2]

MOVE_ORDER: tuple[int, ...] = tuple(sorted(range(COLS), key=lambda c: abs(c - COLS // 2)))


def bit_for_cell(row: int, col: int) -> int:
    """Return the bit corresponding to NumPy board coordinates ``row, col``."""
    if not (0 <= row < ROWS and 0 <= col < COLS):
        raise ValueError(f"cell out of range: ({row}, {col})")
    height_from_bottom = ROWS - 1 - row
    return 1 << (col * STRIDE + height_from_bottom)


def has_alignment(bits: int) -> bool:
    """Return whether ``bits`` contain four connected stones."""
    for shift in (1, STRIDE, STRIDE - 1, STRIDE + 1):
        pair = bits & (bits >> shift)
        if pair & (pair >> (2 * shift)):
            return True
    return False


def compute_winning_positions(bits: int, mask: int) -> int:
    """Return the empty cells that would complete a four-in-a-row of ``bits``.

    Pure bit-mask formula (Pascal Pons): OR the completion cells of the four
    directions, then keep only cells that are currently empty. Cells may be
    at not-yet-playable heights; intersect with ``possible_moves_mask()`` for
    immediately playable wins.
    """
    # Vertical: only the cell above three stacked stones can complete.
    r = (bits << 1) & (bits << 2) & (bits << 3)

    for shift in (STRIDE, STRIDE - 1, STRIDE + 1):  # horizontal, "/", "\"
        p = (bits << shift) & (bits << (2 * shift))
        r |= p & (bits << (3 * shift))
        r |= p & (bits >> shift)
        p = (bits >> shift) & (bits >> (2 * shift))
        r |= p & (bits << shift)
        r |= p & (bits >> (3 * shift))

    return r & (BOARD_MASK ^ mask)


def mirror_bits(bits: int) -> int:
    """Mirror a board bitmap left-right (column c moves to column COLS-1-c)."""
    column_local = (1 << ROWS) - 1
    out = 0
    for c in range(COLS):
        out |= ((bits >> (c * STRIDE)) & column_local) << ((COLS - 1 - c) * STRIDE)
    return out


@dataclass(frozen=True, slots=True)
class BitPosition:
    """Immutable position from the perspective of the player to move."""

    current: int = 0
    mask: int = 0
    moves: int = 0
    to_move: int = 1

    def __post_init__(self) -> None:
        if self.to_move not in (1, 2):
            raise ValueError("to_move must be player 1 or 2")
        if self.current & ~self.mask:
            raise ValueError("current stones must be a subset of mask")
        if self.mask & ~BOARD_MASK:
            raise ValueError("mask contains sentinel/out-of-board bits")
        if self.moves != self.mask.bit_count():
            raise ValueError("moves must match the number of occupied cells")

    @classmethod
    def empty(cls, to_move: int = 1) -> BitPosition:
        return cls(to_move=to_move)

    @classmethod
    def from_board(cls, board: Board, to_move: int) -> BitPosition:
        """Convert a gravity-valid board with exact player IDs into a bitboard."""
        if board.shape != (ROWS, COLS):
            raise ValueError(f"expected board shape {(ROWS, COLS)}, got {board.shape}")
        if to_move not in (1, 2):
            raise ValueError("to_move must be player 1 or 2")

        current = 0
        mask = 0
        for r in range(ROWS):
            for c in range(COLS):
                value = board[r, c]
                if value == EMPTY:
                    continue
                if value not in (1, 2):
                    raise ValueError(f"invalid player id {value} at ({r}, {c})")
                bit = bit_for_cell(r, c)
                mask |= bit
                if value == to_move:
                    current |= bit

        if np.any((board[:-1] != EMPTY) & (board[1:] == EMPTY)):
            raise ValueError("board violates gravity: a token has an empty cell below it")
        return cls(current=current, mask=mask, moves=mask.bit_count(), to_move=to_move)

    @classmethod
    def from_moves(cls, columns: Iterable[int]) -> BitPosition:
        """Build a legal alternating position from zero-based played columns."""
        pos = cls.empty(to_move=1)
        for col in columns:
            if pos.previous_player_won:
                raise ValueError("move sequence continues after a terminal win")
            try:
                column = index(col)
            except TypeError as exc:
                raise ValueError("move columns must be integers") from exc
            pos = pos.played(column)
        return pos

    @property
    def opponent(self) -> int:
        return self.mask ^ self.current

    @property
    def key(self) -> int:
        """Compact relative-position key suitable for a transposition table."""
        return self.current + self.mask

    @property
    def canonical_key(self) -> int:
        """Symmetry-canonical TT key: the position and its mirror share it.

        Connect Four is symmetric under left-right mirroring, so storing
        results under ``min(key, mirrored key)` shares transpositions between
        mirrored subtrees - most valuable in the opening.
        """
        base = self.current + self.mask
        flipped = mirror_bits(self.current) + mirror_bits(self.mask)
        return base if base <= flipped else flipped

    @property
    def is_full(self) -> bool:
        return self.moves >= TOTAL_CELLS

    @property
    def previous_player_won(self) -> bool:
        return has_alignment(self.opponent)

    def can_play(self, col: int) -> bool:
        return 0 <= col < COLS and not bool(self.mask & TOP_MASKS[col])

    def move_bit(self, col: int) -> int:
        if not self.can_play(col):
            return 0
        return (self.mask + BOTTOM_MASKS[col]) & COLUMN_MASKS[col]

    def possible_moves_mask(self) -> int:
        return (self.mask + BOTTOM_MASK) & BOARD_MASK

    def legal_columns(self, *, center_first: bool = True) -> list[int]:
        order = MOVE_ORDER if center_first else tuple(range(COLS))
        return [col for col in order if self.can_play(col)]

    def played(self, col: int) -> BitPosition:
        """Return the position after the current player drops in ``col``."""
        move = self.move_bit(col)
        if move == 0:
            raise ValueError(f"column {col} is full or out of range")
        return BitPosition(
            current=self.current ^ self.mask,
            mask=self.mask | move,
            moves=self.moves + 1,
            to_move=3 - self.to_move,
        )

    def mirror(self) -> BitPosition:
        """Left-right mirrored position (strategically equivalent)."""
        return BitPosition(
            current=mirror_bits(self.current),
            mask=mirror_bits(self.mask),
            moves=self.moves,
            to_move=self.to_move,
        )

    def winning_moves_mask(self) -> int:
        """Playable cells that win immediately for the current player."""
        return compute_winning_positions(self.current, self.mask) & self.possible_moves_mask()

    def winning_columns(self) -> list[int]:
        wins = self.winning_moves_mask()
        return [col for col in MOVE_ORDER if wins & COLUMN_MASKS[col]]

    def non_losing_moves_mask(self) -> int:
        """Moves that win now, or that do not lose on the opponent's next ply.

        Standard exact-solver rule set (Pascal Pons): an immediate win is
        always returned; otherwise, if the opponent has exactly one playable
        winning cell the reply is forced to it, two or more immediate threats
        mean the position is already lost (0 is returned), and any move that
        would make an opponent winning cell playable directly above it is
        excluded.
        """
        wins = self.winning_moves_mask()
        if wins:
            return wins
        possible = self.possible_moves_mask()
        opponent_win = compute_winning_positions(self.opponent, self.mask)
        forced = possible & opponent_win
        if forced:
            if forced & (forced - 1):  # more than one immediate threat
                return 0
            possible = forced
        return possible & ~(opponent_win >> 1)

    def to_board(self) -> Board:
        """Convert back to the public absolute-player NumPy board."""
        board = np.zeros((ROWS, COLS), dtype=np.int8)
        opponent_id = 3 - self.to_move
        for r in range(ROWS):
            for c in range(COLS):
                bit = bit_for_cell(r, c)
                if self.current & bit:
                    board[r, c] = self.to_move
                elif self.opponent & bit:
                    board[r, c] = opponent_id
        return board


__all__ = [
    "BOARD_MASK",
    "BOTTOM_MASK",
    "BOTTOM_MASKS",
    "BitPosition",
    "CENTER_MASK",
    "COLUMN_MASKS",
    "MOVE_ORDER",
    "STRIDE",
    "TOP_MASKS",
    "TOTAL_CELLS",
    "bit_for_cell",
    "compute_winning_positions",
    "has_alignment",
    "mirror_bits",
]
