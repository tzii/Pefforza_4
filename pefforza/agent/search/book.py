"""Exact opening book for the ``impossible`` tier.

Pure-Python search cannot prove the opening interactively (see
docs/search_engine.md), so the strongest tier looks its early moves up
instead. The book is generated offline by ``scripts/build_opening_book.py``
from a native exact solver and holds, for every position in which the AI is
to move up to :attr:`OpeningBook.max_ply` plies *along the lines the AI
itself plays*, a strongly optimal move (fastest win, slowest loss, draw when
neither) and its exact score.

Entries are keyed by :attr:`BitPosition.canonical_key`, so a position and
its mirror share one entry; moves are stored in the canonical orientation
and mirrored back on lookup.

On-disk format (``.xz``-compressed): an 8-byte magic, a little-endian
``uint16`` max ply and ``uint32`` entry count, then three arrays in key
order - ``uint64`` keys (delta-encoded), ``int8`` moves, ``int8`` scores.
"""

from __future__ import annotations

import logging
import lzma
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from pefforza.constants import COLS

from .bitboard import BitPosition

DEFAULT_BOOK_PATH = Path(__file__).resolve().parents[1] / "data" / "opening_book.xz"

logger = logging.getLogger(__name__)

_MAGIC = b"PFZBOOK1"
_HEADER = struct.Struct("<HI")


@dataclass(frozen=True, slots=True)
class BookEntry:
    """A book move for the side to move. ``score`` uses the solver convention:
    0 draw, ``s > 0`` wins with ``s`` of the mover's stones left in hand,
    ``s < 0`` loses."""

    move: int
    score: int


class OpeningBook:
    def __init__(self, keys: np.ndarray, moves: np.ndarray, scores: np.ndarray, max_ply: int):
        if not (len(keys) == len(moves) == len(scores)):
            raise ValueError("keys, moves and scores must have the same length")
        if len(keys) > 1 and not bool(np.all(keys[1:] > keys[:-1])):
            raise ValueError("book keys must be strictly increasing")
        self._keys = keys.astype(np.uint64, copy=False)
        self._moves = moves.astype(np.int8, copy=False)
        self._scores = scores.astype(np.int8, copy=False)
        self.max_ply = int(max_ply)

    # ------------------------------------------------------------ building
    @classmethod
    def from_entries(cls, entries: Mapping[int, tuple[int, int]], max_ply: int) -> OpeningBook:
        """Build from ``{canonical_key: (move_in_canonical_orientation, score)}``."""
        keys = np.array(sorted(entries), dtype=np.uint64)
        moves = np.array([entries[int(k)][0] for k in keys], dtype=np.int8)
        scores = np.array([entries[int(k)][1] for k in keys], dtype=np.int8)
        return cls(keys, moves, scores, max_ply)

    def save(self, path: Path | str) -> None:
        deltas = np.diff(self._keys, prepend=np.uint64(0)).astype("<u8")
        payload = b"".join(
            (
                _MAGIC,
                _HEADER.pack(self.max_ply, len(self._keys)),
                deltas.tobytes(),
                self._moves.tobytes(),
                self._scores.tobytes(),
            )
        )
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(lzma.compress(payload, preset=9 | lzma.PRESET_EXTREME))

    @classmethod
    def load(cls, path: Path | str) -> OpeningBook:
        raw = lzma.decompress(Path(path).read_bytes())
        if raw[: len(_MAGIC)] != _MAGIC:
            raise ValueError(f"{path} is not a Pefforza opening book")
        offset = len(_MAGIC)
        max_ply, count = _HEADER.unpack_from(raw, offset)
        offset += _HEADER.size
        expected = offset + count * 10
        if len(raw) != expected:
            raise ValueError(f"corrupt opening book {path}: {len(raw)} bytes, expected {expected}")
        deltas = np.frombuffer(raw, dtype="<u8", count=count, offset=offset)
        offset += count * 8
        moves = np.frombuffer(raw, dtype=np.int8, count=count, offset=offset)
        scores = np.frombuffer(raw, dtype=np.int8, count=count, offset=offset + count)
        return cls(np.cumsum(deltas, dtype=np.uint64), moves, scores, max_ply)

    # -------------------------------------------------------------- lookup
    def __len__(self) -> int:
        return len(self._keys)

    def lookup(self, position: BitPosition) -> BookEntry | None:
        """The book move for ``position``, or None if it is not in the book."""
        if position.moves > self.max_ply:
            return None
        key = position.canonical_key
        idx = int(np.searchsorted(self._keys, np.uint64(key)))
        if idx >= len(self._keys) or int(self._keys[idx]) != key:
            return None
        move = int(self._moves[idx])
        if position.key != key:  # stored in the mirrored orientation
            move = COLS - 1 - move
        if not position.can_play(move):  # defensive: never return an illegal move
            return None
        return BookEntry(move, int(self._scores[idx]))


@lru_cache(maxsize=1)
def default_book() -> OpeningBook | None:
    """The bundled book, loaded once; None if it is missing or unreadable."""
    try:
        return OpeningBook.load(DEFAULT_BOOK_PATH)
    except (OSError, ValueError, lzma.LZMAError) as exc:
        logger.warning("Opening book unavailable (%s); the opening falls back to search.", exc)
        return None
