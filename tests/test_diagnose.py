"""Headless tests for the live vision diagnostic tool."""

from __future__ import annotations

import numpy as np

from pefforza.constants import COLS, ROWS
from pefforza.vision import diagnose


def test_annotate_draws_on_a_copy():
    img = np.zeros((600, 700, 3), dtype=np.uint8)
    grid = np.zeros((ROWS, COLS), dtype=np.int8)
    grid[ROWS - 1, 0] = 1
    grid[ROWS - 1, 1] = 2
    out = diagnose._annotate(img, grid, np.full((ROWS, COLS), 0.5, np.float32), 700, 600)
    assert out.shape == img.shape
    assert out.any()
    assert not img.any()


class _Capture:
    def __init__(self, frames: int, opened: bool = True) -> None:
        self.frames = frames
        self.opened = opened

    def isOpened(self) -> bool:
        return self.opened

    def read(self):
        if self.frames <= 0:
            return False, None
        self.frames -= 1
        return True, np.zeros((600, 700, 3), dtype=np.uint8)

    def release(self) -> None:
        pass


def _patch(monkeypatch, capture, keys, calibrated=True):
    key_iter = iter(keys)
    monkeypatch.setattr(diagnose.cv2, "VideoCapture", lambda _i: capture)
    monkeypatch.setattr(diagnose.cv2, "waitKey", lambda _ms: next(key_iter, ord("q")))
    monkeypatch.setattr(diagnose.cv2, "imshow", lambda *_a: None)
    monkeypatch.setattr(diagnose.cv2, "destroyAllWindows", lambda: None)
    saved = []
    monkeypatch.setattr(diagnose.cv2, "imwrite", lambda path, img: saved.append(path) or True)

    def calibrate(self, cap, flip=False):
        if calibrated:
            self.set_corners([[0, 0], [700, 0], [700, 600], [0, 600]])
        return calibrated

    monkeypatch.setattr(diagnose.BoardDetector, "calibrate", calibrate)
    return saved


def test_main_streams_pauses_saves_and_quits(monkeypatch):
    saved = _patch(monkeypatch, _Capture(5), [-1, ord("s"), ord(" "), ord(" "), ord("q")])
    assert diagnose.main(["--flip"]) == 0
    assert saved == ["vision_debug.png"]


def test_main_error_paths(monkeypatch):
    _patch(monkeypatch, _Capture(5, opened=False), [])
    assert diagnose.main([]) == 2
    _patch(monkeypatch, _Capture(5), [], calibrated=False)
    assert diagnose.main([]) == 1
    _patch(monkeypatch, _Capture(0), [])
    assert diagnose.main([]) == 0
