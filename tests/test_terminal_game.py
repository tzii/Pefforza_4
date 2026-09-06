"""Play the terminal loop with synthetic input and no model or audio device."""

from __future__ import annotations

import random

import pytest

from pefforza.cli import play_cli


def test_human_input_retries_typos_ranges_and_full_columns(monkeypatch, capsys):
    answers = iter(["hello", "0", "8", "1", " 4 "])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    assert play_cli.get_human_action([3, 5]) == 3
    output = capsys.readouterr().out
    assert "Invalid input" in output
    assert "between 1 and 7" in output
    assert "column is full" in output


@pytest.mark.parametrize("action", [0.0, -1])
def test_bad_ai_action_falls_back_without_ending_the_game(monkeypatch, capsys, action):
    monkeypatch.setattr("builtins.input", lambda prompt: "4")
    monkeypatch.setattr(play_cli, "build_opponent", lambda *a, **kw: lambda b, p, v: action)
    assert play_cli.main(["--difficulty", "easy"]) == 0
    output = capsys.readouterr().out
    assert "Human wins." in output
    assert "invalid move" not in output


@pytest.mark.parametrize("interrupt", [EOFError, KeyboardInterrupt])
def test_terminal_interrupt_is_clean_and_closes_environment(monkeypatch, capsys, interrupt):
    closed = []

    def stop(prompt):
        raise interrupt

    monkeypatch.setattr("builtins.input", stop)
    monkeypatch.setattr(play_cli.Connect4Env, "close", lambda self: closed.append(True))
    assert play_cli.main(["--difficulty", "easy"]) == 130
    assert "Game interrupted." in capsys.readouterr().out
    assert closed == [True]


def test_terminal_isolates_the_board_and_valid_columns_from_agents(monkeypatch, capsys):
    def destructive_agent(board, player, valid):
        board[:] = player
        valid.clear()
        return -1

    monkeypatch.setattr("builtins.input", lambda prompt: "4")
    monkeypatch.setattr(play_cli, "build_opponent", lambda *a, **kw: destructive_agent)
    assert play_cli.main(["--difficulty", "easy"]) == 0
    assert "Human wins." in capsys.readouterr().out


def test_terminal_seed_does_not_modify_global_random_state(monkeypatch):
    state = random.getstate()

    def stop(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", stop)
    assert play_cli.main(["--difficulty", "easy", "--seed", "17"]) == 130
    assert random.getstate() == state
