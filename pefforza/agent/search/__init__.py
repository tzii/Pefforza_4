"""Bitboard search engines: the ``hard`` depth engine and the exact solver."""

from .alphabeta import BitboardSearchAgent, BitSearchResult
from .bitboard import BitPosition
from .book import BookEntry, OpeningBook, default_book
from .perfect import (
    PerfectResult,
    PerfectSearchTimeoutError,
    PerfectSolver,
    RootResult,
    opening_fallback_move,
)

__all__ = [
    "BitPosition",
    "BookEntry",
    "OpeningBook",
    "BitSearchResult",
    "BitboardSearchAgent",
    "PerfectResult",
    "PerfectSearchTimeoutError",
    "PerfectSolver",
    "RootResult",
    "default_book",
    "opening_fallback_move",
]
