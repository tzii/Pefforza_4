"""End-to-end tests of the terminal and Pygame game loops.

Human input is scripted (``input()`` for the CLI, a fake ``pygame.event.get``
for the GUI) and Pygame runs on SDL's dummy video driver, so no terminal,
window, audio device, or trained model is needed.
"""

from __future__ import annotations

import builtins
import itertools
import logging
import os

import numpy as np
import pytest

from pefforza.constants import COLS, ROWS


def _scripted_input(monkeypatch, answers):
    it = iter(answers)

    def fake_input(prompt: str = "") -> str:
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr(builtins, "input", fake_input)


# ---------------------------------------------------------------- play_cli
@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_cli_full_game_terminates(monkeypatch, capsys, difficulty):
    from pefforza.cli import play_cli

    monkeypatch.setenv("PEFFORZA_TTS_BACKEND", "null")
    # Garbage, out-of-range, then every column forever: exercises the
    # validation branches and guarantees the game reaches an end state.
    _scripted_input(monkeypatch, itertools.chain(["abc", "9"], itertools.cycle("1234567")))
    rc = play_cli.main(["--difficulty", difficulty, "--seed", "0", "--voice"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Please enter a number." in out
    assert "between 1 and 7" in out
    assert "wins." in out or "draw" in out


def test_cli_reports_full_column(monkeypatch, capsys):
    from pefforza.cli import play_cli

    valid = [c for c in range(COLS) if c != 0]
    _scripted_input(monkeypatch, ["1", "2"])
    assert play_cli.get_human_action(valid) == 1
    assert "column is full" in capsys.readouterr().out


def test_cli_eof_is_a_clean_interrupt(monkeypatch):
    from pefforza.cli import play_cli

    _scripted_input(monkeypatch, [])
    assert play_cli.main(["--difficulty", "easy", "--seed", "0"]) == 130


def test_print_board_renders_tokens(capsys):
    from pefforza.cli.play_cli import print_board

    board = np.zeros((ROWS, COLS), dtype=np.int8)
    board[ROWS - 1, 0] = 1
    board[ROWS - 1, 1] = 2
    print_board(board)
    assert "| X O" in capsys.readouterr().out


# ---------------------------------------------------------------- play_gui
@pytest.fixture
def headless_pygame(monkeypatch, tmp_path):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.chdir(tmp_path)  # play_gui writes watchdog.log to the cwd
    pygame = pytest.importorskip("pygame")
    waits: list[int] = []
    monkeypatch.setattr(pygame.time, "wait", lambda ms: waits.append(ms) or 0)
    yield pygame, waits
    # play_gui reconfigures the root logger with a FileHandler; close it so
    # the temporary directory can be removed on Windows.
    root = logging.getLogger()
    for handler in list(root.handlers):
        if isinstance(handler, logging.FileHandler):
            root.removeHandler(handler)
            handler.close()


def _click_script(pygame, max_calls: int = 400):
    """Fake ``pygame.event.get``: hover + click each column in turn, then QUIT."""
    from pefforza.cli.play_gui import SQUARESIZE

    calls = itertools.count()
    columns = itertools.cycle(range(COLS))

    def fake_get(*_args, **_kwargs):
        if next(calls) >= max_calls:
            return [pygame.event.Event(pygame.QUIT)]
        x = next(columns) * SQUARESIZE + SQUARESIZE // 2
        return [
            pygame.event.Event(pygame.MOUSEMOTION, pos=(x, 10)),
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, 10), button=1),
        ]

    return fake_get


@pytest.mark.parametrize("animate", [False, True])
def test_gui_full_game_reaches_game_over(headless_pygame, monkeypatch, animate):
    pygame, waits = headless_pygame
    from pefforza.cli import play_gui

    monkeypatch.setattr(pygame.event, "get", _click_script(pygame))
    argv = ["--difficulty", "medium", "--seed", "0"]
    if not animate:
        argv.append("--no-animate")
    assert play_gui.main(argv) == 0
    # The game-over screen is held with pygame.time.wait before returning.
    assert waits, "game never reached the game-over screen"
    assert os.path.exists("watchdog.log")


def test_gui_quit_event_exits(headless_pygame, monkeypatch):
    pygame, waits = headless_pygame
    from pefforza.cli import play_gui

    monkeypatch.setattr(pygame.event, "get", _click_script(pygame, max_calls=0))
    assert play_gui.main(["--difficulty", "easy", "--no-animate"]) == 0
    assert waits == []


def test_watchdog_flags_an_ignored_block():
    from pefforza.cli.play_gui import watchdog_diagnostic

    board = np.zeros((ROWS, COLS), dtype=np.int8)
    board[ROWS - 1, 0:3] = 1  # human threatens column 3
    board[ROWS - 2, 0:2] = 2
    message = watchdog_diagnostic(board, 6, "easy")
    assert message is not None
    assert "Human could win at column 3, AI played 6" in message
    assert watchdog_diagnostic(board, 3, "easy") is None


def test_watchdog_accepts_taking_own_win_over_blocking():
    from pefforza.cli.play_gui import watchdog_diagnostic

    board = np.zeros((ROWS, COLS), dtype=np.int8)
    board[ROWS - 1, 0:3] = 1  # human threatens column 3
    board[ROWS - 1, 4] = 1
    for r in range(ROWS - 3, ROWS):
        board[r, 6] = 2  # AI threatens vertically in column 6
    assert watchdog_diagnostic(board, 6, "easy") is None
    assert watchdog_diagnostic(board, 5, "easy") is not None


def test_no_watchdog_without_a_threat():
    from pefforza.cli.play_gui import watchdog_diagnostic

    board = np.zeros((ROWS, COLS), dtype=np.int8)
    assert watchdog_diagnostic(board, 0, "easy") is None
