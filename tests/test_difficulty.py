"""Tests for the difficulty registry."""

from __future__ import annotations

from pathlib import Path

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


class _StubModel:
    """Minimal stand-in for a loaded SB3 PPO model."""

    def predict(self, obs, deterministic: bool = True):  # noqa: ARG002
        import numpy as np

        # SB3 returns a 0-d action array for a single observation.
        return np.array(3), None


def test_neural_uses_model_when_checkpoint_loads(tmp_path: Path, monkeypatch):
    dummy = tmp_path / "model.zip"
    dummy.write_bytes(b"stub")
    monkeypatch.setattr("stable_baselines3.PPO.load", staticmethod(lambda path: _StubModel()))
    agent = build_opponent("neural", model_path=dummy)
    assert agent(empty_board(), 1, list(range(COLS))) == 3


def test_neural_falls_back_to_heuristic_when_load_fails(tmp_path: Path, monkeypatch):
    """A corrupt checkpoint must degrade to the heuristic, never crash."""
    dummy = tmp_path / "model.zip"
    dummy.write_bytes(b"stub")

    def _explode(path):
        raise RuntimeError("corrupt checkpoint")

    monkeypatch.setattr("stable_baselines3.PPO.load", staticmethod(_explode))
    agent = build_opponent("neural", model_path=dummy)
    assert 0 <= agent(empty_board(), 1, list(range(COLS))) < COLS
