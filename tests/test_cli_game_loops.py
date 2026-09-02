"""Unit tests for the interactive input loops and the scripted CLI game flow.

The terminal entrypoint pre-validates every human move so a typo never ends
the game, and falls back to a legal column if an agent ever returns an
illegal one. These tests pin that contract and drive ``play_cli.main``
end-to-end with scripted stdin and a deterministic opponent. No display,
camera, audio device, or trained model is needed.
"""

from __future__ import annotations

import builtins

from pefforza.cli import play_cli, play_physical


class _ScriptedInput:
    """Replaces ``builtins.input`` with a queued list of lines."""

    def __init__(self, *lines: str) -> None:
        self.lines = list(lines)

    def __call__(self, prompt: str = "") -> str:  # noqa: ARG001
        if not self.lines:
            raise EOFError
        return self.lines.pop(0)


# ---------------------------------------------------------------- play_cli


def test_get_human_action_accepts_valid_column(monkeypatch):
    monkeypatch.setattr(builtins, "input", _ScriptedInput("4"))
    assert play_cli.get_human_action([0, 1, 2, 3, 4, 5, 6]) == 3


def test_get_human_action_reprompts_non_numeric(monkeypatch, capsys):
    monkeypatch.setattr(builtins, "input", _ScriptedInput("abc", "4"))
    assert play_cli.get_human_action(list(range(7))) == 3
    assert "Invalid input" in capsys.readouterr().out


def test_get_human_action_reprompts_out_of_range(monkeypatch, capsys):
    monkeypatch.setattr(builtins, "input", _ScriptedInput("0", "8", "4"))
    assert play_cli.get_human_action(list(range(7))) == 3
    out = capsys.readouterr().out
    assert out.count("between 1 and 7") == 2


def test_get_human_action_reprompts_full_column(monkeypatch, capsys):
    monkeypatch.setattr(builtins, "input", _ScriptedInput("4", "3"))
    # Column index 3 is not in valid but is in range: reported as full.
    assert play_cli.get_human_action([0, 2]) == 2
    assert "column is full" in capsys.readouterr().out


def test_print_board_renders_header_and_pieces(capsys):
    import numpy as np

    board = np.zeros((6, 7), dtype=np.int8)
    board[5, 0] = 1
    board[4, 1] = 2
    play_cli.print_board(board)
    out = capsys.readouterr().out
    assert "1 2 3 4 5 6 7" in out
    assert "X" in out and "O" in out


def test_main_scripted_human_win(monkeypatch, capsys):
    """Human stacking column 1 four times must win against a rightmost AI."""
    monkeypatch.setattr(
        play_cli,
        "build_opponent",
        lambda name, seed=None, model_path=None: lambda board, my_id, valid: valid[-1],
    )
    monkeypatch.setattr(builtins, "input", _ScriptedInput(*(["1"] * 4)))

    rc = play_cli.main(["--difficulty", "easy"])
    assert rc == 0
    assert "Human wins." in capsys.readouterr().out


def test_main_eof_during_input_returns_130(monkeypatch, capsys):
    monkeypatch.setattr(builtins, "input", _ScriptedInput())  # immediate EOF
    assert play_cli.main([]) == 130
    assert "interrupted" in capsys.readouterr().out


# ----------------------------------------------------------- play_physical


def test_prompt_ai_color_parses_choices(monkeypatch, capsys):
    monkeypatch.setattr(builtins, "input", _ScriptedInput("1"))
    assert play_physical._prompt_ai_color() is True

    monkeypatch.setattr(builtins, "input", _ScriptedInput("2"))
    assert play_physical._prompt_ai_color() is False

    monkeypatch.setattr(builtins, "input", _ScriptedInput("x", "9", "1"))
    assert play_physical._prompt_ai_color() is True
    assert capsys.readouterr().out.count("Invalid choice.") == 2
