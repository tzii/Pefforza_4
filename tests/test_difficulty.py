"""Tests for the difficulty registry."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pefforza.agent.difficulty import (
    DEFAULT_DIFFICULTY,
    DIFFICULTIES,
    DIFFICULTY_NAMES,
    build_opponent,
    describe_difficulties,
)
from pefforza.constants import COLS
from pefforza.rules import empty_board


def test_registry_contains_expected_tiers():
    assert {"easy", "medium", "hard", "impossible"} <= set(DIFFICULTIES)
    assert "neural" in DIFFICULTY_NAMES
    assert DEFAULT_DIFFICULTY in DIFFICULTY_NAMES


def test_hard_backend_is_the_bitboard_engine():
    """`hard` must stay backed by the bitboard engine (plan PR3); the matrix
    engine remains only as the differential-test baseline."""
    assert "Bitboard alpha-beta" in DIFFICULTIES["hard"].description


@pytest.mark.parametrize("name", ["easy", "medium", "hard", "impossible"])
def test_build_opponent_returns_playable_agent(name: str):
    agent = build_opponent(name, seed=0)
    board = empty_board()
    col = agent(board, 1, list(range(COLS)))
    assert 0 <= col < COLS


def test_neural_falls_back_to_heuristic_when_model_missing(tmp_path: Path):
    bogus = tmp_path / "no-such-model.zip"
    agent = build_opponent("neural", seed=0, model_path=bogus)
    # Falls back gracefully; must still return a legal move.
    col = agent(empty_board(), 1, list(range(COLS)))
    assert 0 <= col < COLS


def test_unknown_difficulty_raises():
    with pytest.raises(ValueError):
        build_opponent("godlike")


def test_describe_difficulties_lists_all_tiers():
    text = describe_difficulties()
    for name in ("easy", "medium", "hard", "impossible", "neural"):
        assert name in text


@pytest.mark.parametrize("failure", ["missing", "import", "load"])
def test_neural_fallback_reports_medium_without_requiring_a_model(tmp_path, monkeypatch, failure):
    path = tmp_path / "model.zip"
    if failure != "missing":
        path.write_bytes(b"test fixture")

    def fail_load(*args):
        raise ValueError("Invalid checkpoint")

    module = None if failure == "import" else SimpleNamespace(PPO=SimpleNamespace(load=fail_load))
    monkeypatch.setitem(sys.modules, "stable_baselines3", module)
    notifications = []
    agent = build_opponent("neural", model_path=path, on_fallback=notifications.append)
    assert notifications == ["medium"]
    assert agent(empty_board(), 1, list(range(COLS))) == COLS // 2
