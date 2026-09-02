"""Unit tests for the pluggable TTS backend.

These tests use the in-process ``RecordingBackend`` so they don't require an
audio device, ``pyttsx3``, or any OS-level TTS driver.
"""

from __future__ import annotations

import threading
import time

import pytest

from pefforza.interaction.voice import (
    NullBackend,
    TTSBackend,
    VoiceEngine,
)


class RecordingBackend(TTSBackend):
    def __init__(self) -> None:
        self.utterances: list[str] = []
        self.closed = False
        self._spoken = threading.Event()

    def speak(self, text: str) -> None:
        self.utterances.append(text)
        self._spoken.set()

    def close(self) -> None:
        self.closed = True

    def wait(self, timeout: float = 1.0) -> bool:
        return self._spoken.wait(timeout)


def _make_engine(backend: TTSBackend) -> VoiceEngine:
    return VoiceEngine(backend=backend)


def test_speak_routes_to_backend():
    backend = RecordingBackend()
    engine = _make_engine(backend)
    try:
        engine.speak("hello world")
        assert backend.wait()
        # Drain by shutting down so we observe the close hook deterministically.
    finally:
        engine.shutdown()
    assert backend.utterances == ["hello world"]
    assert backend.closed is True


def test_empty_text_is_dropped():
    backend = RecordingBackend()
    engine = _make_engine(backend)
    try:
        engine.speak("")
        # Empty string must never reach the backend.
        time.sleep(0.05)
        assert backend.utterances == []
    finally:
        engine.shutdown()


def test_play_move_commentary_includes_confidence_phrase():
    backend = RecordingBackend()
    engine = _make_engine(backend)
    try:
        engine.play_move_commentary(2, confidence=0.95)
        assert backend.wait()
    finally:
        engine.shutdown()
    assert "column 3" in backend.utterances[0]
    assert "Too easy" in backend.utterances[0]


class _ExplodingBackend(TTSBackend):
    def __init__(self) -> None:
        self.calls = 0

    def speak(self, text: str) -> None:
        self.calls += 1
        raise RuntimeError("driver missing")


def test_backend_failure_is_fail_soft():
    """A failing backend must not propagate; subsequent speaks are dropped."""
    backend = _ExplodingBackend()
    engine = _make_engine(backend)
    try:
        engine.speak("first")
        # Give the worker a moment to consume and fail.
        time.sleep(0.05)
        # After the failure, the engine becomes unavailable; speak() must
        # return immediately and not enqueue further work.
        engine.speak("second")
        time.sleep(0.05)
    finally:
        engine.shutdown()
    assert backend.calls == 1


def test_null_backend_is_noop():
    backend = NullBackend()
    # Should not raise.
    backend.speak("anything")


def test_env_var_selects_null_backend(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PEFFORZA_TTS_BACKEND", "null")
    engine = VoiceEngine()
    try:
        # Should not raise even on machines without pyttsx3 / audio.
        engine.speak("ignored")
        time.sleep(0.05)
    finally:
        engine.shutdown()


def test_low_confidence_commentary_says_tricky():
    backend = RecordingBackend()
    engine = _make_engine(backend)
    try:
        engine.play_move_commentary(0, confidence=0.2)
        assert backend.wait()
    finally:
        engine.shutdown()
    assert "column 1" in backend.utterances[0]
    assert "Hmm, tricky." in backend.utterances[0]


def test_shutdown_is_idempotent():
    engine = _make_engine(RecordingBackend())
    engine.shutdown()
    # Second shutdown: worker thread already gone, must return quietly.
    engine.shutdown()


def test_pyttsx3_init_failure_disables_engine(monkeypatch: pytest.MonkeyPatch):
    """When the default backend cannot initialize, the engine goes inert."""

    class _RaisingBackend:
        def __init__(self, rate: int = 150) -> None:
            raise RuntimeError("no audio device")

    monkeypatch.setattr("pefforza.interaction.voice.Pyttsx3Backend", _RaisingBackend)
    engine = VoiceEngine()
    try:
        time.sleep(0.1)  # let the worker resolve (and fail) the backend
        engine.speak("never spoken")
        assert engine._available is False
    finally:
        engine.shutdown()
