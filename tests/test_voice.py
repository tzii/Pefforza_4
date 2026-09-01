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
