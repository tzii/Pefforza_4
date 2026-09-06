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


def test_speak_after_shutdown_does_not_queue_or_restart():
    backend = RecordingBackend()
    engine = _make_engine(backend)
    engine.speak("before shutdown")
    engine.shutdown()
    engine.speak("after shutdown")
    engine.shutdown()
    assert backend.utterances == ["before shutdown"]
    assert engine._queue.empty()


def test_timed_out_shutdown_can_be_joined_again():
    release = threading.Event()

    class BlockingBackend(RecordingBackend):
        def speak(self, text: str) -> None:
            super().speak(text)
            assert release.wait(2)

    backend = BlockingBackend()
    engine = _make_engine(backend)
    worker = engine._thread
    try:
        engine.speak("first")
        assert backend.wait()
        engine.shutdown(timeout=0)
        engine.speak("too late")
        assert engine._thread is worker
    finally:
        release.set()
        engine.shutdown()
    assert not worker.is_alive()
    assert backend.closed
    assert backend.utterances == ["first"]
    assert engine._queue.empty()


def test_close_failure_is_logged_without_unhandled_thread_error(caplog):
    class BrokenCloseBackend(RecordingBackend):
        def close(self) -> None:
            raise RuntimeError("cleanup failed")

    engine = _make_engine(BrokenCloseBackend())
    engine.shutdown()
    assert "cleanup failed" in caplog.text
    assert engine._queue.empty()


def test_shutdown_during_failed_backend_cleanup_leaves_no_sentinel():
    closing = threading.Event()
    release = threading.Event()

    class FailedBackend(RecordingBackend):
        def speak(self, text: str) -> None:
            raise RuntimeError("speaker disconnected")

        def close(self) -> None:
            closing.set()
            assert release.wait(2)
            super().close()

    backend = FailedBackend()
    engine = _make_engine(backend)
    try:
        engine.speak("hello")
        assert closing.wait(1)
        engine.shutdown(timeout=0)
        engine.speak("too late")
    finally:
        release.set()
        engine.shutdown()
    assert backend.closed
    assert engine._queue.empty()


def test_worker_start_failure_disables_voice_and_closes_backend(monkeypatch, caplog):
    def fail_start(self):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(threading.Thread, "start", fail_start)
    backend = RecordingBackend()
    engine = _make_engine(backend)
    engine.speak("ignored")
    engine.shutdown()
    engine.shutdown()
    assert engine._thread is None
    assert engine._queue.empty()
    assert backend.closed
    assert "can't start new thread" in caplog.text


def test_worker_start_and_backend_cleanup_failures_remain_fail_soft(monkeypatch, caplog):
    def fail_start(self):
        raise RuntimeError("can't start new thread")

    class BrokenCloseBackend(RecordingBackend):
        def close(self) -> None:
            raise RuntimeError("cleanup failed")

    monkeypatch.setattr(threading.Thread, "start", fail_start)
    engine = _make_engine(BrokenCloseBackend())
    engine.shutdown()
    assert "can't start new thread" in caplog.text
