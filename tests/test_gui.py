"""Native GUI behavior, without a real screen, audio device, or trained model."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from pefforza.cli import play_gui
from pefforza.cli.gui_view import (
    BOARD_X,
    BOARD_Y,
    HEIGHT,
    RED,
    WIDTH,
    GameView,
    cell_center,
    column_at,
    map_pointer,
    viewport,
)
from pefforza.constants import ROWS
from scripts.preview_gui import parse_event


class FakeWorker:
    def __init__(self, *args, **kwargs):
        self.busy = False
        self.error = None
        self.result = None
        self.requests = 0
        self.closed = False

    def request(self, board, player):
        self.busy = True
        self.requests += 1

    def poll(self):
        result = self.result
        if result is not None:
            self.result = None
            self.busy = False
        return result

    def cancel(self):
        self.busy = False
        self.result = None

    def close(self):
        self.closed = True
        self.cancel()


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(play_gui, "OpponentWorker", FakeWorker)
    instance = play_gui.GameApp(animate=False)
    yield instance
    instance.close()


def key(app, value, now=0):
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=value), now)


def test_keyboard_and_ai_turn_ignore_duplicate_input(app):
    key(app, pygame.K_4)
    key(app, pygame.K_5)
    assert app.session.moves == [3]
    app.tick(0)
    app.tick(1)
    assert app.worker.requests == 1
    app.worker.result = 2
    app.tick(2)
    assert app.session.moves == [3, 2]
    assert app.session.current_player == 1


def test_arrows_enter_and_space_use_selected_column(app):
    key(app, pygame.K_RIGHT)
    key(app, pygame.K_RETURN)
    assert app.session.moves == [4]
    key(app, pygame.K_r)
    key(app, pygame.K_LEFT)
    key(app, pygame.K_SPACE)
    assert app.session.moves == [3]


def test_restart_during_search_discards_the_pending_result(app):
    key(app, pygame.K_4)
    app.tick(0)
    app.worker.result = 2
    key(app, pygame.K_r)
    app.tick(10)
    assert app.session.moves == []
    assert not app.worker.busy


def test_undo_during_search_and_after_ai_reply(app):
    key(app, pygame.K_4)
    app.tick(0)
    key(app, pygame.K_u)
    assert app.session.moves == []
    key(app, pygame.K_2)
    app.tick(10)
    app.worker.result = 5
    app.tick(20)
    key(app, pygame.K_u)
    assert app.session.moves == []
    assert app.session.current_player == 1


def test_animation_is_nonblocking_and_can_be_cancelled_without_undoing_old_moves(app):
    app.session.play(3)
    app.session.play(2)
    app.animate = True
    key(app, pygame.K_5, now=100)
    app.tick(101)
    assert app.animation is not None
    assert app.session.moves == [3, 2]
    key(app, pygame.K_u, now=102)
    app.tick(1000)
    assert app.animation is None
    assert app.session.moves == [3, 2]
    assert app.worker.requests == 0


def test_animation_commits_exactly_one_drop(app):
    app.animate = True
    key(app, pygame.K_4, now=100)
    key(app, pygame.K_4, now=101)
    app.tick(100 + app.animation_duration)
    assert app.session.moves == [3]
    assert app.worker.requests == 1


def test_hint_and_full_column_preserve_board(app):
    key(app, pygame.K_h)
    assert app.hint_col == 3
    assert "center" in app.session.status
    assert not app.session.board.any()
    for _ in range(ROWS):
        app.session.play(0)
    board = app.session.board.copy()
    key(app, pygame.K_1)
    assert "full" in app.notice
    np.testing.assert_array_equal(app.session.board, board)
    assert not app.session.game_over


def test_hint_and_keyboard_drop_always_share_the_highlighted_column(app):
    app.selected_col = 0
    key(app, pygame.K_h)
    assert app.hint_col == app.selected_col == 3
    key(app, pygame.K_RIGHT)
    assert app.hint_col is None
    assert app.selected_col == 4
    key(app, pygame.K_RETURN)
    assert app.session.moves == [4]


def test_pointer_selection_clears_the_old_hint_highlight(app):
    key(app, pygame.K_h)
    app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=cell_center(0, 5)), 0)
    assert app.hint_col is None
    assert app.selected_col == 5


def test_results_stay_visible_until_player_chooses_replay(app):
    for col in [0, 6, 1, 6, 2, 5, 3]:
        app.session.play(col)
    app.tick(100_000)
    key(app, pygame.K_5)
    assert app.running
    assert app.session.winner == 1
    assert len(app.session.moves) == 7
    key(app, pygame.K_r)
    assert not app.session.game_over


def test_difficulty_change_stops_old_worker_and_starts_a_fresh_round(app):
    old_worker = app.worker
    key(app, pygame.K_4)
    key(app, pygame.K_d)
    assert old_worker.closed
    assert app.difficulty == "impossible"
    assert not app.session.moves


@pytest.mark.parametrize("event", [pygame.QUIT, pygame.KEYDOWN])
def test_quit_never_waits_for_a_move(app, event):
    key(app, pygame.K_4)
    app.handle_event(pygame.event.Event(event, key=pygame.K_ESCAPE), 0)
    app.tick(0)
    assert not app.running
    assert app.worker.requests == 0


def test_pointer_hit_targets_and_letterboxing(app):
    assert column_at((BOARD_X - 1, BOARD_Y)) is None
    assert column_at(cell_center(0, 6)) == 6
    area = viewport((WIDTH // 2, HEIGHT // 2 + 100))
    assert area.y == 50
    x, y = cell_center(0, 4)
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x // 2, y // 2 + 50), button=1)
    mapped = map_pointer(event, area)
    app.handle_event(mapped, 0)
    assert app.session.moves == [4]
    event.pos = (0, 0)
    assert map_pointer(event, area) is None


def test_right_click_does_not_play(app):
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=cell_center(0, 3), button=3)
    app.handle_event(event, 0)
    assert not app.session.moves


def test_render_opening_hint_and_finished_game(app):
    pygame.font.init()
    try:
        view = GameView()
        screen = pygame.Surface((WIDTH, HEIGHT))
        view.draw(screen, app, 0)
        key(app, pygame.K_h)
        view.draw(screen, app, 1)
        for col in [0, 6, 1, 6, 2, 5, 3]:
            app.session.play(col)
        view.draw(screen, app, 2)
        x, y = cell_center(ROWS - 1, 0)
        assert screen.get_at((x + 15, y))[:3] == RED
    finally:
        pygame.font.quit()


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "key", "key": "Escape"},
        {"kind": "click", "x": -1, "y": 0},
        {"kind": "move", "x": WIDTH, "y": 0},
        {"kind": "click", "x": True, "y": 0},
        {"kind": "other"},
    ],
)
def test_preview_rejects_unsupported_input(payload):
    with pytest.raises(ValueError):
        parse_event(payload)


def test_preview_translates_only_game_input():
    event = parse_event({"kind": "key", "key": "4"})
    assert event.type == pygame.KEYDOWN and event.key == pygame.K_4
    event = parse_event({"kind": "click", "x": 80, "y": 240})
    assert event.pos == (80, 240) and event.button == 1
