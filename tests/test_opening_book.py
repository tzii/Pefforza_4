"""Opening book: storage format, symmetry handling, coverage, and tier wiring."""

from __future__ import annotations

import random
import time

import numpy as np
import pytest

from pefforza.agent.difficulty import exact_agent
from pefforza.agent.search import BitPosition, OpeningBook, PerfectSolver, default_book
from pefforza.agent.search import book as book_module


def _tiny_book() -> tuple[OpeningBook, BitPosition]:
    # Position after the first player opens in column 1: asymmetric, so its
    # canonical key belongs to exactly one of the two orientations.
    pos = BitPosition.from_moves([1])
    canonical = pos if pos.key == pos.canonical_key else pos.mirror()
    return OpeningBook.from_entries({canonical.canonical_key: (2, 5)}, max_ply=4), canonical


def test_round_trip_preserves_entries(tmp_path):
    book, canonical = _tiny_book()
    path = tmp_path / "book.xz"
    book.save(path)
    loaded = OpeningBook.load(path)
    assert len(loaded) == 1
    assert loaded.max_ply == 4
    entry = loaded.lookup(canonical)
    assert entry is not None and (entry.move, entry.score) == (2, 5)


def test_lookup_mirrors_moves_for_the_mirrored_orientation():
    book, canonical = _tiny_book()
    mirrored = canonical.mirror()
    assert mirrored.key != canonical.key
    entry = book.lookup(mirrored)
    assert entry is not None and entry.move == 4


def test_lookup_misses_unknown_and_too_deep_positions():
    book, _ = _tiny_book()
    assert book.lookup(BitPosition.from_moves([3])) is None
    assert book.lookup(BitPosition.from_moves([3, 3, 3, 3, 2])) is None


def test_corrupt_or_foreign_files_are_rejected(tmp_path):
    import lzma

    foreign = tmp_path / "foreign.xz"
    foreign.write_bytes(lzma.compress(b"not a book"))
    with pytest.raises(ValueError):
        OpeningBook.load(foreign)

    book, _ = _tiny_book()
    path = tmp_path / "book.xz"
    book.save(path)
    truncated = tmp_path / "truncated.xz"
    truncated.write_bytes(lzma.compress(lzma.decompress(path.read_bytes())[:-1]))
    with pytest.raises(ValueError):
        OpeningBook.load(truncated)


def test_keys_must_be_strictly_increasing():
    keys = np.array([5, 5], dtype=np.uint64)
    with pytest.raises(ValueError):
        OpeningBook(keys, np.zeros(2, np.int8), np.zeros(2, np.int8), max_ply=1)


def test_missing_bundled_book_degrades_to_search(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(book_module, "DEFAULT_BOOK_PATH", tmp_path / "absent.xz")
    book_module.default_book.cache_clear()
    try:
        assert book_module.default_book() is None
        assert "Opening book unavailable" in caplog.text
    finally:
        book_module.default_book.cache_clear()


# ------------------------------------------------------------ bundled book
@pytest.fixture(scope="module")
def bundled():
    book = default_book()
    assert book is not None, "the bundled opening book must load"
    return book


def test_bundled_book_covers_the_documented_depth(bundled):
    assert bundled.max_ply == 17
    assert len(bundled) > 100_000
    first = bundled.lookup(BitPosition.empty())
    # Only the center column wins from the empty board.
    assert first is not None and first.move == 3 and first.score > 0


@pytest.mark.parametrize("ai_first", [True, False])
def test_book_is_closed_under_any_opponent_reply(bundled, ai_first):
    """Following its own book, the AI never leaves it before ``max_ply``."""
    rng = random.Random(7)
    for _ in range(150):
        pos = BitPosition.empty()
        while pos.moves <= bundled.max_ply and not pos.is_full:
            ai_to_move = (pos.moves % 2 == 0) == ai_first
            if ai_to_move:
                entry = bundled.lookup(pos)
                assert entry is not None, f"off-book at ply {pos.moves}"
                col = entry.move
            else:
                col = rng.choice(pos.legal_columns())
            pos = pos.played(col)
            if pos.previous_player_won:
                break


def test_impossible_tier_answers_from_the_book_without_search(bundled, monkeypatch):
    def no_search(*_args, **_kwargs):
        raise AssertionError("book positions must not reach the solver")

    monkeypatch.setattr(PerfectSolver, "solve_root", no_search)
    agent = exact_agent(book=bundled)
    board = BitPosition.empty().to_board()
    start = time.perf_counter()
    assert agent(board, 1, list(range(7))) == 3
    assert time.perf_counter() - start < 0.5


def test_impossible_tier_without_book_still_plays_legally():
    agent = exact_agent(book=None, time_budget=0.05)
    board = BitPosition.from_moves([3, 3]).to_board()
    assert agent(board, 1, list(range(7))) in range(7)
