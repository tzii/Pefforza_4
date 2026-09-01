"""Unit tests for the pure game-logic helpers."""

from __future__ import annotations

import numpy as np
import pytest

from pefforza.constants import COLS, ROWS
from pefforza.rules import (
    available_columns,
    check_winner,
    empty_board,
    is_board_full,
    is_column_full,
    next_open_row,
    swap_perspective,
)


def test_empty_board_shape_and_dtype():
    b = empty_board()
    assert b.shape == (ROWS, COLS)
    assert b.dtype == np.int8
    assert (b == 0).all()


def test_available_columns_full_and_partial():
    b = empty_board()
    assert available_columns(b) == list(range(COLS))
    b[:, 0] = 1
    assert 0 not in available_columns(b)
    assert is_column_full(b, 0)
    assert not is_column_full(b, 1)


def test_next_open_row_falls_to_bottom_then_stacks():
    b = empty_board()
    assert next_open_row(b, 3) == ROWS - 1
    b[ROWS - 1, 3] = 1
    assert next_open_row(b, 3) == ROWS - 2


def test_next_open_row_returns_minus_one_when_full():
    b = empty_board()
    b[:, 4] = 2
    assert next_open_row(b, 4) == -1


def test_is_board_full():
    b = empty_board()
    assert not is_board_full(b)
    b[:] = 1
    assert is_board_full(b)


def test_check_winner_horizontal():
    b = empty_board()
    b[5, 0:4] = 1
    assert check_winner(b) == 1


def test_check_winner_vertical():
    b = empty_board()
    b[2:6, 2] = 2
    assert check_winner(b) == 2


def test_check_winner_diagonal_down_right():
    b = empty_board()
    for i in range(4):
        b[i, i] = 1
    assert check_winner(b) == 1


def test_check_winner_diagonal_up_right():
    b = empty_board()
    for i in range(4):
        b[5 - i, i] = 2
    assert check_winner(b) == 2


def test_check_winner_no_winner():
    b = empty_board()
    b[5, 0:3] = 1
    b[5, 3] = 2
    assert check_winner(b) == 0


@pytest.mark.parametrize("player", [1, 2])
def test_swap_perspective_round_trip(player):
    b = empty_board()
    b[5, 0] = player
    b[4, 1] = 3 - player
    swapped = swap_perspective(b)
    assert swapped[5, 0] == 3 - player
    assert swapped[4, 1] == player
    # Empty cells stay empty.
    assert (swapped == 0).sum() == ROWS * COLS - 2
    # Round-trip is identity.
    np.testing.assert_array_equal(swap_perspective(swapped), b)
