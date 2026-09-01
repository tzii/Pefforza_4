"""Differential tests for the new bitboard search foundation."""

from __future__ import annotations

import numpy as np

from pefforza.agent.minimax import MinimaxAgent, evaluate_position
from pefforza.agent.search import BitboardSearchAgent, BitPosition, PerfectSolver
from pefforza.agent.search.heuristic import evaluate_bit_position
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
