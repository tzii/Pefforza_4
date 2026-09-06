"""Differential tests for the new bitboard search foundation."""

from __future__ import annotations

import random

import numpy as np
import pytest

from pefforza.agent.minimax import MinimaxAgent, evaluate_position
from pefforza.agent.search import BitboardSearchAgent, BitPosition, PerfectSolver
from pefforza.agent.search.heuristic import evaluate_bit_position
from pefforza.constants import COLS
from pefforza.rules import check_winner, empty_board, next_open_row


def _board_from_moves(columns: list[int]):
    board = empty_board()
    player = 1
    for col in columns:
        row = next_open_row(board, col)
        assert row >= 0
        board[row, col] = player
        assert check_winner(board) == 0
        player = 3 - player
    return board, player


def test_bitposition_round_trip_preserves_absolute_board():
    columns = [3, 2, 3, 4, 1, 5, 0, 6, 2, 2]
    board, to_move = _board_from_moves(columns)
    position = BitPosition.from_board(board, to_move=to_move)
    np.testing.assert_array_equal(position.to_board(), board)
    assert position.moves == len(columns)
    assert position.to_move == to_move


def test_bitposition_play_matches_matrix_gravity_and_turn_swap():
    columns = [3, 3, 2, 4, 2, 4]
    board, to_move = _board_from_moves(columns)
    position = BitPosition.from_board(board, to_move=to_move)

    col = 2
    row = next_open_row(board, col)
    board[row, col] = to_move
    child = position.played(col)

    np.testing.assert_array_equal(child.to_board(), board)
    assert child.to_move == 3 - to_move


def test_bitboard_heuristic_matches_legacy_matrix_heuristic():
    columns = [3, 2, 3, 4, 1, 5, 2, 4, 6, 1]
    board, to_move = _board_from_moves(columns)
    position = BitPosition.from_board(board, to_move=to_move)
    assert evaluate_bit_position(position) == evaluate_position(board, to_move)


def test_bitboard_depth_limited_search_matches_corrected_legacy_engine():
    positions = [
        [],
        [3, 2, 3, 4],
        [3, 2, 4, 3, 1, 5],
        [2, 3, 2, 3, 4, 1, 5, 4],
    ]
    for moves in positions:
        board, to_move = _board_from_moves(moves)
        legacy = MinimaxAgent(depth=5, seed=0).search(board, to_move, depth=5)
        bit = BitboardSearchAgent(depth=5, use_tt=True).search(board, to_move, depth=5)
        assert (bit.column, bit.score) == (legacy.column, legacy.score)


def test_transposition_table_does_not_change_depth_limited_result():
    board, to_move = _board_from_moves([3, 2, 4, 3, 1, 5, 2, 4])
    cached = BitboardSearchAgent(depth=6, use_tt=True).search(board, to_move)
    uncached = BitboardSearchAgent(depth=6, use_tt=False).search(board, to_move)
    assert (cached.column, cached.score) == (uncached.column, uncached.score)
    assert cached.nodes <= uncached.nodes


# ------------------------------------------------------------ random corpus
def _random_corpus(seed: int = 20260901, count: int = 12, max_plies: int = 14):
    """Deterministic corpus of distinct, non-terminal legal positions.

    Seeded random play generates positions no developer hand-picked, which is
    exactly what a differential baseline needs: the two engines must agree
    everywhere, not just on cute tactical setups.
    """
    rng = random.Random(seed)
    positions = []
    seen: set[bytes] = set()
    while len(positions) < count:
        board = empty_board()
        player = 1
        plies = rng.randint(2, max_plies)
        for _ in range(plies):
            valid = [c for c in range(COLS) if board[0, c] == 0]
            col = rng.choice(valid)
            row = next_open_row(board, col)
            board[row, col] = player
            if check_winner(board) != 0:
                break
            player = 3 - player
        if check_winner(board) != 0:
            continue
        key = board.tobytes()
        if key in seen:
            continue
        seen.add(key)
        positions.append((board.copy(), player))
    return positions


def test_matrix_and_bitboard_engines_agree_on_random_corpus():
    """Same heuristic + same depth => same score and same best move (14.2)."""
    for board, to_move in _random_corpus():
        legacy = MinimaxAgent(depth=5, seed=0).search(board, to_move, depth=5)
        bit = BitboardSearchAgent(depth=5, use_tt=True).search(board, to_move, depth=5)
        assert bit.score == legacy.score, f"score drift at to_move={to_move}"
        assert bit.column == legacy.column


def test_tt_on_and_off_agree_on_random_corpus():
    """The transposition table may save nodes but must never change results."""
    for board, to_move in _random_corpus():
        cached = BitboardSearchAgent(depth=7, use_tt=True).search(board, to_move, depth=7)
        uncached = BitboardSearchAgent(depth=7, use_tt=False).search(board, to_move, depth=7)
        assert cached.score == uncached.score
        assert cached.column == uncached.column


def test_mirror_positions_preserve_score_and_mirror_best_move():
    """Connect 4 is left-right symmetric: mirrored positions must return the
    mirrored best move at the same score (14.2)."""
    for board, to_move in _random_corpus():
        engine = BitboardSearchAgent(depth=6, use_tt=True)
        base = engine.search(board, to_move, depth=6)
        mirrored = engine.search(np.ascontiguousarray(board[:, ::-1]), to_move, depth=6)
        assert mirrored.score == base.score
        assert mirrored.column == COLS - 1 - base.column


def test_reused_engine_matches_fresh_engine_across_a_game():
    """The `hard` backend reuses one engine (and its TT) for a whole game;
    entries carried over from earlier searches must stay sound."""
    rng = random.Random(7)
    reused = BitboardSearchAgent(depth=6, use_tt=True)
    board = empty_board()
    player = 1
    for _ in range(12):
        if check_winner(board) != 0 or not any(board[0, c] == 0 for c in range(COLS)):
            break
        fresh = BitboardSearchAgent(depth=6, use_tt=True)
        r_reused = reused.search(board, player, depth=6)
        r_fresh = fresh.search(board, player, depth=6)
        assert (r_reused.column, r_reused.score) == (r_fresh.column, r_fresh.score)
        # Play a slightly randomized legal move so the game tree varies.
        valid = [c for c in range(COLS) if board[0, c] == 0]
        col = r_reused.column if rng.random() < 0.7 else rng.choice(valid)
        board[next_open_row(board, col), col] = player
        player = 3 - player


def test_deeper_cached_search_does_not_change_requested_depth():
    board, player = _board_from_moves([3, 2, 4, 3, 1, 5, 2, 4])
    reused = BitboardSearchAgent()
    reused.search(board, player, depth=6)
    for depth in (2, 3, 4):
        expected = BitboardSearchAgent(use_tt=False).search(board, player, depth=depth)
        actual = reused.search(board, player, depth=depth)
        assert (actual.column, actual.score) == (expected.column, expected.score)
        assert reused.analyze(board, player, depth=depth) == BitboardSearchAgent(
            use_tt=False
        ).analyze(board, player, depth=depth)


def test_cached_mate_distance_is_relative_to_the_new_root():
    board = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0],
            [0, 0, 1, 1, 0, 0, 1],
            [1, 2, 2, 2, 0, 2, 2],
            [2, 1, 2, 2, 1, 1, 1],
        ],
        dtype=np.int8,
    )
    parent = BitPosition.from_board(board, to_move=2)
    reused = BitboardSearchAgent()
    reused.search(board, parent.to_move, depth=6)
    child = parent.played(4)
    expected = BitboardSearchAgent(use_tt=False).search(child.to_board(), child.to_move, depth=5)
    actual = reused.search(child.to_board(), child.to_move, depth=5)
    assert abs(expected.score) > 99_900
    assert (actual.column, actual.score) == (expected.column, expected.score)


@pytest.mark.parametrize("player,score", [(1, 100_000), (2, -100_000)])
def test_search_does_not_play_after_a_win(player, score):
    board = BitPosition.from_moves([0, 6, 1, 6, 2, 6, 3]).to_board()
    bit = BitboardSearchAgent(depth=2)
    result = bit.search(board, player)
    assert (result.column, result.score, result.nodes) == (-1, score, 0)
    assert bit.analyze(board, player) == {}
    matrix = MinimaxAgent(depth=2)
    result = matrix.search(board, player, depth=2)
    assert (result.column, result.score, result.nodes) == (-1, score, 0)
    result = matrix.search_with_time_budget(board, player, time_budget=1e-9)
    assert (result.column, result.score, result.nodes) == (-1, score, 0)


@pytest.mark.parametrize("depth", [0, -1])
def test_analyze_rejects_non_positive_depth(depth):
    with pytest.raises(ValueError, match="depth"):
        BitboardSearchAgent().analyze(empty_board(), 1, depth=depth)


def test_perfect_solver_matches_independently_verified_late_game_scores():
    # Expected scores were cross-checked against a separate exhaustive brute-
    # force implementation during development. Positive = forced win, zero =
    # draw, negative = forced loss; magnitude is distance-to-end scoring.
    cases = {
        "6434456774276433175332347726": -2,
        "11147773432527414565547711452253": 0,
        "12653346553665641172561773334152": 1,
        "4322644436262111677772276567334": -3,
    }
    solver = PerfectSolver()
    for one_based_moves, expected in cases.items():
        position = BitPosition.from_moves(int(ch) - 1 for ch in one_based_moves)
        result = solver.solve(position, weak=False)
        assert result.score == expected


def test_perfect_solver_weak_mode_normalizes_to_win_draw_loss():
    cases = {
        "6434456774276433175332347726": -1,
        "11147773432527414565547711452253": 0,
        "12653346553665641172561773334152": 1,
    }
    for one_based_moves, expected in cases.items():
        position = BitPosition.from_moves(int(ch) - 1 for ch in one_based_moves)
        assert PerfectSolver().solve(position, weak=True).score == expected
