"""Best-effort, pluggable text-to-speech.

Design goals (per ``AGENTS.md``):

* **Fail-soft.** Any TTS failure (missing driver, no audio device, OS-specific
  quirks) is logged once and the engine becomes a no-op. Voice errors must
  never crash the game.
* **Pluggable.** TTS backends implement :class:`TTSBackend`. Default backend is
  ``pyttsx3`` (offline, cross-platform, MPL-2.0, actively maintained). A
  ``null`` backend is provided for tests / headless environments. Future
  backends (e.g. ``piper``, cloud APIs) can be added without touching
  ``VoiceEngine``.
* **Thread-safe.** ``pyttsx3`` engines are not reliably thread-safe, so a
  single dedicated daemon worker drains a queue.
"""

from __future__ import annotations

import contextlib
import logging
import os
import queue
import threading
from abc import ABC, abstractmethod
from typing import Final

logger = logging.getLogger(__name__)

_SHUTDOWN: Final[object] = object()


# --------------------------------------------------------------------- backends
class TTSBackend(ABC):
    """Minimal contract for a text-to-speech backend."""

    @abstractmethod
    def speak(self, text: str) -> None:
        """Synchronously speak ``text``. Raise on failure."""

    def close(self) -> None:  # noqa: B027 - intentionally optional, default no-op
        """Optional resource cleanup."""


class NullBackend(TTSBackend):
    """No-op backend. Used when TTS is disabled or unavailable."""

    def speak(self, text: str) -> None:  # noqa: D401 - trivial
        logger.debug("NullBackend.speak: %r", text)


class Pyttsx3Backend(TTSBackend):
    """``pyttsx3`` backend. Lazy import so missing TTS doesn't break import."""

    def __init__(self, rate: int = 150) -> None:
        import pyttsx3  # local import: optional dependency at runtime

        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", rate)

    def speak(self, text: str) -> None:
        self._engine.say(str(text))
        self._engine.runAndWait()

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._engine.stop()


# ----------------------------------------------------------------------- engine
class VoiceEngine:
    """Non-blocking, fail-soft text-to-speech engine."""

    def __init__(
        self,
        rate: int = 150,
        backend: TTSBackend | None = None,
    ) -> None:
        self._rate = rate
        self._explicit_backend = backend
        self._queue: queue.Queue[object] = queue.Queue()
        self._available = True
        self._stopping = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._start_worker()

    # ------------------------------------------------------------------ API
    def speak(self, text: str) -> None:
        """Queue ``text`` for speech. Returns immediately."""
        with self._lock:
            if not self._available or not text:
                return
            self._queue.put(str(text))

    def play_move_commentary(self, col: int, confidence: float | None = None) -> None:
        msg = f"Putting in column {col + 1}"
        if confidence is not None:
            if confidence > 0.8:
                msg += ". Too easy."
            elif confidence < 0.4:
                msg += ". Hmm, tricky."
        self.speak(msg)

    def shutdown(self, timeout: float = 2.0) -> None:
        """Signal the worker to stop and wait briefly for it to drain."""
        with self._lock:
            worker = self._thread
            if worker is None:
                self._available = False
                return
            if self._available and not self._stopping and worker.is_alive():
                self._stopping = True
                self._queue.put(_SHUTDOWN)
            self._available = False
        # A timed-out worker stays joinable; never enqueue speech after its sentinel.
        if worker is not threading.current_thread():
            worker.join(timeout=timeout)
        with self._lock:
            if not worker.is_alive():
                self._thread = None

    # ----------------------------------------------------------- internals
    def _resolve_backend(self) -> TTSBackend | None:
        if self._explicit_backend is not None:
            return self._explicit_backend
        # Allow tests / CI / headless setups to disable TTS without code change.
        if os.environ.get("PEFFORZA_TTS_BACKEND", "").lower() == "null":
            return NullBackend()
        try:
            return Pyttsx3Backend(rate=self._rate)
        except Exception as exc:
            logger.warning("Voice disabled: pyttsx3 init failed (%s)", exc)
            return None

    def _start_worker(self) -> None:
        self._thread = threading.Thread(
            target=self._worker_loop,
            name="pefforza-voice",
            daemon=True,
        )
        try:
            self._thread.start()
        except RuntimeError as exc:
            logger.warning("Voice disabled: worker could not start (%s)", exc)
            self._available = False
            self._thread = None
            if self._explicit_backend is not None:
                with contextlib.suppress(Exception):
                    self._explicit_backend.close()

    def _worker_loop(self) -> None:
        backend = self._resolve_backend()
        try:
            if backend is None:
                return
            while True:
                item = self._queue.get()
                if item is _SHUTDOWN:
                    break
                try:
                    backend.speak(str(item))
                except Exception as exc:
                    logger.warning(
                        "TTS speak failed (%s); disabling further speech.",
                        exc,
                    )
                    break
        finally:
            with self._lock:
                self._available = False
                while True:
                    try:
                        self._queue.get_nowait()
                    except queue.Empty:
                        break
            if backend is not None:
                try:
                    backend.close()
                except Exception as exc:
                    logger.warning("TTS cleanup failed (%s).", exc)


__all__ = ["NullBackend", "Pyttsx3Backend", "TTSBackend", "VoiceEngine"]
