"""Search boundaries reject malformed positions instead of inventing a game."""

from __future__ import annotations

import numpy as np
import pytest

from pefforza.agent.search import BitPosition
from pefforza.constants import COLS, ROWS
from pefforza.rules import empty_board


@pytest.mark.parametrize("value", [0.5, 1.9, 2.1, np.nan, np.inf, -1, 3, "1"])
def test_board_conversion_rejects_non_player_values(value):
    board = empty_board().astype(object)
    board[-1, 3] = value
    with pytest.raises(ValueError, match="player id"):
        BitPosition.from_board(board, to_move=1)


@pytest.mark.parametrize("column", range(COLS))
@pytest.mark.parametrize("row", range(ROWS - 1))
def test_board_conversion_rejects_floating_tokens(row, column):
    board = empty_board()
    board[row, column] = 1
    with pytest.raises(ValueError, match="gravity"):
        BitPosition.from_board(board, to_move=2)


def test_board_conversion_preserves_supported_stacks_and_player_perspective():
    board = empty_board()
    for column in range(COLS):
        height = min(column, ROWS)
        if height:
            board[-height:, column] = [1 + i % 2 for i in range(height)]
    before = board.copy()
    for player in (1, 2):
        position = BitPosition.from_board(board, to_move=player)
        np.testing.assert_array_equal(position.to_board(), before)
    np.testing.assert_array_equal(board, before)


@pytest.mark.parametrize("column", [0.5, 1.9, "3", None])
def test_move_sequence_rejects_non_integer_columns(column):
    with pytest.raises(ValueError, match="integer"):
        BitPosition.from_moves([column])


def test_move_sequence_accepts_numpy_integer_columns():
    position = BitPosition.from_moves(np.array([3, 2, 3], dtype=np.int64))
    assert position.moves == 3
    assert position.to_move == 2


def test_move_sequence_rejects_play_after_a_win():
    with pytest.raises(ValueError, match="terminal"):
        BitPosition.from_moves([0, 6, 1, 6, 2, 6, 3, 5])


def test_move_sequence_may_finish_on_the_winning_move():
    position = BitPosition.from_moves([0, 6, 1, 6, 2, 6, 3])
    assert position.moves == 7
    assert position.previous_player_won
