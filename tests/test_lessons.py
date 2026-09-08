"""Verify lesson answers by exploring every legal move and tactical reply."""

import pytest

from pefforza.cli.gui_game import GameSession
from pefforza.cli.lessons import LESSONS
from pefforza.rules import available_columns, check_winner, next_open_row, tactically_safe_columns


def after(board, column, player):
    result = board.copy()
    result[next_open_row(result, column), column] = player
    return result


def wins(board, player):
    return {
        column
        for column in available_columns(board)
        if check_winner(after(board, column, player)) == player
    }


@pytest.mark.parametrize("lesson", LESSONS, ids=lambda lesson: lesson.title)
def test_every_lesson_is_reachable_and_its_answer_set_is_complete(lesson):
    game = GameSession()
    for column in lesson.moves:
        assert not game.game_over
        assert game.play(column)
    assert game.current_player == 1
    assert not game.game_over
    board = game.board.copy()
    if lesson.goal == "win":
        expected = wins(board, 1)
    elif lesson.goal in ("block", "safe"):
        assert not wins(board, 1)
        assert bool(wins(board, 2)) == (lesson.goal == "block")
        expected = {
            column for column in available_columns(board) if not wins(after(board, column, 1), 2)
        }
        assert set(available_columns(board)) - expected
        assert set(tactically_safe_columns(board, 1)) == expected
        assert game.hint() in lesson.answers
    else:
        assert lesson.goal == "fork"
        assert not wins(board, 1) and not wins(board, 2)
        expected = set()
        for column in available_columns(board):
            moved = after(board, column, 1)
            if len(wins(moved, 1)) >= 2 and not wins(moved, 2):
                # Every opponent reply must leave an immediate human win.
                assert all(wins(after(moved, reply, 2), 1) for reply in available_columns(moved))
                expected.add(column)
    assert set(lesson.answers) == expected


@pytest.mark.parametrize("index,dr,dc", [(0, 0, 1), (1, -1, 0), (2, 1, 1)])
def test_win_lesson_matches_the_advertised_direction(index, dr, dc):
    lesson = LESSONS[index]
    game = GameSession()
    for column in (*lesson.moves, lesson.answers[0]):
        assert game.play(column)
    cells = set(game.winning_cells)
    assert any(all((r + i * dr, c + i * dc) in cells for i in range(4)) for r, c in cells)


def test_fork_has_the_two_explained_open_ends():
    game = GameSession()
    for column in (*LESSONS[4].moves, LESSONS[4].answers[0]):
        game.play(column)
    assert wins(game.board, 1) == {2, 6}
