"""Phase-2 tests for the exact solver (plan sections 6.1-6.4 and 14.3).

Covers the bit-mask move generation (differential against a brute-force
reference), symmetry canonicalization, the fixed-size transposition table,
and the solver's mathematical invariants. No webcam, model, or display is
involved; everything runs on seeded random legal positions.
"""

from __future__ import annotations

import random

from pefforza.agent.search import BitPosition, PerfectSolver
from pefforza.agent.search.bitboard import (
    COLUMN_MASKS,
    TOTAL_CELLS,
    compute_winning_positions,
    has_alignment,
    mirror_bits,
)
from pefforza.constants import COLS, ROWS
from pefforza.rules import empty_board


def _random_positions(
    seed: int = 20260902, count: int = 40, require_search: bool = False
) -> list[BitPosition]:
    """Seeded corpus of distinct, non-terminal positions (12-26 plies).

    Shallower positions are excluded on purpose: exact-solving near the
    opening is the PR5 opening-book problem, not something a test corpus
    should attempt. With ``require_search=True`` only positions where the
    side to move has no immediate win and is not already lost are kept, so
    solver tests exercise real search instead of terminal short-circuits.
    """
    rng = random.Random(seed)
    out: list[BitPosition] = []
    seen: set[int] = set()
    while len(out) < count:
        pos = BitPosition.empty()
        for _ in range(rng.randint(12, 26)):
            legal = pos.legal_columns(center_first=False)
            if not legal:
                break
            pos = pos.played(rng.choice(legal))
            if pos.previous_player_won:
                break
        if pos.previous_player_won or pos.is_full:
            continue
        if require_search and (pos.winning_moves_mask() or pos.non_losing_moves_mask() == 0):
            continue
        if pos.key in seen:
            continue
        seen.add(pos.key)
        out.append(pos)
    return out


def _solver_corpus() -> list[BitPosition]:
    """Five deeper, tactically open positions: real search at CI-friendly cost."""
    return [pos for pos in _random_positions(require_search=True) if pos.moves >= 18][:5]


def _bruteforce_playable_wins(pos: BitPosition) -> int:
    mask = 0
    for col in range(COLS):
        bit = pos.move_bit(col)
        if bit and has_alignment(pos.current | bit):
            mask |= bit
    return mask


def _bruteforce_non_losing(pos: BitPosition) -> int:
    """The pre-phase-2 implementation: immediate wins, else keep the moves
    whose child gives the opponent no immediate win."""
    wins = _bruteforce_playable_wins(pos)
    if wins:
        return wins
    safe = 0
    for col in pos.legal_columns(center_first=False):
        if pos.played(col).winning_moves_mask() == 0:
            safe |= pos.move_bit(col)
    return safe


# ------------------------------------------------------------ move generation
def test_winning_moves_match_bruteforce_on_corpus():
    for pos in _random_positions():
        expected = _bruteforce_playable_wins(pos)
        got = compute_winning_positions(pos.current, pos.mask) & pos.possible_moves_mask()
        assert got == expected


def test_winning_moves_agree_with_played_position_check():
    for pos in _random_positions()[:8]:
        for col in pos.legal_columns(center_first=False):
            wins_now = pos.played(col).previous_player_won
            via_mask = bool(
                compute_winning_positions(pos.current, pos.mask)
                & pos.possible_moves_mask()
                & COLUMN_MASKS[col]
            )
            assert wins_now == via_mask


def test_non_losing_moves_match_bruteforce_on_corpus():
    for pos in _random_positions():
        assert pos.non_losing_moves_mask() == _bruteforce_non_losing(pos)


def test_single_threat_forces_the_block():
    board = empty_board()
    board[ROWS - 1, 0:3] = 1  # red three on the floor: only column 3 blocks
    board[ROWS - 1, 5] = 2
    board[ROWS - 2, 5] = 2
    pos = BitPosition.from_board(board, to_move=2)  # yellow to move
    assert pos.non_losing_moves_mask() == pos.move_bit(3)


def test_double_threat_is_lost_immediately():
    board = empty_board()
    board[ROWS - 1, 0:3] = 1  # red horizontal three -> threat at column 3
    board[ROWS - 1, 6] = 1
    board[ROWS - 2, 6] = 1
    board[ROWS - 3, 6] = 1  # red vertical three -> threat on top of column 6
    board[ROWS - 1, 4] = 1  # seventh red for move parity
    # Six yellows with no alignment of their own (three scattered pairs).
    board[ROWS - 1, 5] = 2
    board[ROWS - 2, 5] = 2
    board[ROWS - 2, 4] = 2
    board[ROWS - 3, 4] = 2
    board[ROWS - 2, 0] = 2
    board[ROWS - 2, 1] = 2
    pos = BitPosition.from_board(board, to_move=2)
    assert pos.non_losing_moves_mask() == 0
    assert PerfectSolver(table_size_bits=10).solve(pos, weak=True).score == -1


def test_move_that_opens_a_win_above_is_excluded():
    board = empty_board()
    board[4, 0:3] = 1  # red three on the second row: wins at (4,3) once playable
    board[ROWS - 1, 2] = 1  # fourth red (gravity support + parity)
    board[ROWS - 1, 0] = 2
    board[ROWS - 1, 1] = 2
    board[ROWS - 1, 5] = 2  # three yellows, no threat of their own
    pos = BitPosition.from_board(board, to_move=2)
    safe = pos.non_losing_moves_mask()
    # Dropping at column 3 makes (4,3) playable and red wins there at once.
    assert not safe & COLUMN_MASKS[3]
    for col in pos.legal_columns(center_first=False):
        if col != 3:
            assert safe & COLUMN_MASKS[col]


# ---------------------------------------------------------------- symmetry
def test_mirror_is_an_involution_preserving_structure():
    for pos in _random_positions()[:10]:
        mirrored = pos.mirror()
        assert mirrored.mirror() == pos
        assert mirrored.moves == pos.moves
        assert mirrored.to_move == pos.to_move
        assert mirror_bits(pos.current) == mirrored.current


def test_canonical_key_shared_with_mirror():
    for pos in _random_positions():
        assert pos.canonical_key == pos.mirror().canonical_key


def test_canonical_key_distinguishes_different_positions():
    corpus = _random_positions()[:20]
    assert len({pos.canonical_key for pos in corpus}) > len(corpus) // 2


# ------------------------------------------------------------------- solver
def test_solver_mirror_positions_score_equal():
    for pos in _solver_corpus():
        a = PerfectSolver(table_size_bits=14).solve(pos, weak=True)
        b = PerfectSolver(table_size_bits=14).solve(pos.mirror(), weak=True)
        assert a.score == b.score


def test_weak_and_strong_scores_agree_on_sign():
    for pos in _solver_corpus():
        weak = PerfectSolver(table_size_bits=14).solve(pos, weak=True)
        strong = PerfectSolver(table_size_bits=14).solve(pos, weak=False)
        assert (strong.score > 0) - (strong.score < 0) == weak.score


def test_tiny_transposition_table_returns_same_scores():
    for pos in _solver_corpus():
        big = PerfectSolver(table_size_bits=16).solve(pos, weak=True)
        tiny = PerfectSolver(table_size_bits=4).solve(pos, weak=True)
        assert tiny.score == big.score


def test_solver_is_deterministic():
    pos = _solver_corpus()[0]
    a = PerfectSolver(table_size_bits=12).solve(pos, weak=True)
    b = PerfectSolver(table_size_bits=12).solve(pos, weak=True)
    assert (a.score, a.nodes) == (b.score, b.nodes)


def test_strong_score_within_mathematical_bounds():
    for pos in _solver_corpus():
        r = PerfectSolver(table_size_bits=14).solve(pos, weak=False)
        limit = (TOTAL_CELLS + 1 - pos.moves) // 2
        assert -limit <= r.score <= limit


def test_analyze_scores_are_mirror_symmetric():
    corpus = _random_positions(require_search=True)
    pos = max(corpus, key=lambda p: p.moves)  # deepest: cheapest to solve fully
    solver = PerfectSolver(table_size_bits=14)
    scores = solver.analyze(pos, weak=True)
    mirrored = solver.analyze(pos.mirror(), weak=True)
    for col, score in scores.items():
        assert mirrored[COLS - 1 - col] == score
