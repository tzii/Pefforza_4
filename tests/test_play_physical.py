"""Headless tests for the physical-board decision path (no camera, no window)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from pefforza.cli.play_physical import (
    PhysicalAssistant,
    StableGridFilter,
    _parse_args,
)
from pefforza.constants import COLS, ROWS

REPO_ROOT = Path(__file__).resolve().parents[1]


def _grid(*drops: tuple[int, int]) -> np.ndarray:
    """Build a vision grid (1 = red, 2 = yellow) from ``(column, color)`` drops."""
    grid = np.zeros((ROWS, COLS), dtype=np.int8)
    for col, color in drops:
        row = max(r for r in range(ROWS) if grid[r, col] == 0)
        grid[row, col] = color
    return grid


class RecordingAgent:
    def __init__(self, move: int) -> None:
        self.move = move
        self.calls: list[tuple[np.ndarray, int, list[int]]] = []

    def __call__(self, board, player, valid):
        self.calls.append((board.copy(), player, list(valid)))
        return self.move


def test_ai_red_moves_on_empty_board_with_unswapped_view():
    agent = RecordingAgent(3)
    result = PhysicalAssistant(agent, ai_is_red=True).analyze(_grid())
    assert result.kind == "move"
    assert result.display_col == 3
    board, player, valid = agent.calls[0]
    assert player == 1
    assert valid == list(range(COLS))
    assert not board.any()


def test_ai_yellow_waits_for_red_then_sees_itself_as_player_one():
    agent = RecordingAgent(2)
    assistant = PhysicalAssistant(agent, ai_is_red=False)
    assert assistant.analyze(_grid()).kind == "wait"
    assert agent.calls == []

    result = assistant.analyze(_grid((3, 1)))
    assert result.kind == "move"
    board, _, _ = agent.calls[0]
    # Yellow AI: the red token must appear as the opponent (2) in agent view.
    assert board[ROWS - 1, 3] == 2


def test_rejected_reading_never_reaches_the_agent():
    agent = RecordingAgent(0)
    assistant = PhysicalAssistant(agent, ai_is_red=True)
    floating = np.zeros((ROWS, COLS), dtype=np.int8)
    floating[0, 0] = 1
    result = assistant.analyze(floating)
    assert result.kind == "rejected"
    assert "gravity" in result.message
    assert agent.calls == []


def test_illegal_agent_move_is_replaced_by_a_legal_one():
    full_col = [(0, 1 if i % 2 == 0 else 2) for i in range(ROWS)]
    assistant = PhysicalAssistant(RecordingAgent(0), ai_is_red=True)
    result = assistant.analyze(_grid(*full_col))
    assert result.kind == "move"
    assert result.display_col == 1


def test_game_over_is_reported_with_winner():
    red_wins = _grid((0, 1), (0, 2), (1, 1), (1, 2), (2, 1), (2, 2), (3, 1))
    result = PhysicalAssistant(RecordingAgent(0), ai_is_red=False).analyze(red_wins)
    assert result.kind == "game_over"
    assert result.winner == 1
    assert result.message == "RED WINS!"


def test_cleared_board_after_game_over_resyncs_and_reset_forgets_history():
    red_wins = _grid((0, 1), (0, 2), (1, 1), (1, 2), (2, 1), (2, 2), (3, 1))
    assistant = PhysicalAssistant(RecordingAgent(3), ai_is_red=True)
    assistant.analyze(red_wins)
    assert assistant.analyze(_grid()).kind == "resynced"

    assistant.analyze(_grid((3, 1), (3, 2)))
    # A board that does not follow from the tracked history is rejected...
    jumped = _grid((0, 1), (0, 2), (1, 1), (1, 2))
    assert assistant.analyze(jumped).kind == "rejected"
    # ...until tracking is reset.
    assistant.reset()
    assert assistant.analyze(jumped).kind == "move"


def test_stable_filter_emits_once_per_settled_reading():
    stable = StableGridFilter(frames=3)
    empty = _grid()
    one = _grid((3, 1))
    assert stable.update(empty) is None
    assert stable.update(empty) is None
    emitted = stable.update(empty)
    assert emitted is not None and np.array_equal(emitted, empty)
    # The same settled board is not re-emitted.
    assert stable.update(empty) is None
    # A flicker resets the streak; only a sustained new reading is emitted.
    assert stable.update(one) is None
    assert stable.update(empty) is None
    assert stable.update(one) is None
    assert stable.update(one) is None
    assert np.array_equal(stable.update(one), one)


def test_stable_filter_lost_frame_breaks_streak_and_reset_reemits():
    stable = StableGridFilter(frames=2)
    empty = _grid()
    assert stable.update(empty) is None
    assert stable.update(None) is None
    assert stable.update(empty) is None
    assert stable.update(empty) is not None
    stable.reset()
    stable.update(empty)
    assert stable.update(empty) is not None


def test_stable_filter_rejects_non_positive_window():
    with pytest.raises(ValueError):
        StableGridFilter(frames=0)


def test_parse_args_watch_defaults_and_overrides():
    args = _parse_args(["--watch", "--voice", "--ai-color", "yellow", "--no-voice"])
    assert args.watch is True
    assert args.voice is False
    assert args.ai_color == "yellow"
    assert args.stable_frames >= 1
    with pytest.raises(SystemExit):
        _parse_args(["--stable-frames", "0"])


def test_main_shim_help_smoke():
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "--watch" in result.stdout
