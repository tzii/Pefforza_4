"""Automatic board localization and color adaptation on rendered scenes.

Scenes are synthesized in code: a blue frame with margins and a stand, 42
round holes (dark when empty, red/yellow tokens otherwise), placed into a
cluttered background under a perspective transform, optionally dimmed. No
webcam needed. Real photos can be added as labelled fixtures - see
``test_labelled_photo_fixtures``.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from pefforza.constants import COLS, ROWS
from pefforza.vision.board_detector import (
    BoardDetector,
    ColorProfile,
    _wrapped_hue_ranges,
    locate_board,
)

FIXTURES = Path(__file__).parent / "fixtures" / "vision"

_BLUE = (190, 90, 20)
_HOLE = (45, 40, 40)
_RED = (40, 40, 220)
_YELLOW = (40, 220, 220)

PITCH = 60
MARGIN = 28
STAND = 70


def _sample_grid() -> np.ndarray:
    grid = np.zeros((ROWS, COLS), dtype=np.int8)
    for col, color in [(3, 1), (3, 2), (2, 1), (4, 2), (0, 1), (6, 2), (3, 1)]:
        row = max(r for r in range(ROWS) if grid[r, col] == 0)
        grid[row, col] = color
    return grid


def _render_board(grid: np.ndarray) -> np.ndarray:
    """Front-on board image: frame margins on all sides plus a stand below."""
    h = ROWS * PITCH + 2 * MARGIN + STAND
    w = COLS * PITCH + 2 * MARGIN
    img = np.full((h, w, 3), _BLUE, dtype=np.uint8)
    for r in range(ROWS):
        for c in range(COLS):
            center = (MARGIN + c * PITCH + PITCH // 2, MARGIN + r * PITCH + PITCH // 2)
            color = {0: _HOLE, 1: _RED, 2: _YELLOW}[int(grid[r, c])]
            cv2.circle(img, center, int(PITCH * 0.38), color, -1, lineType=cv2.LINE_AA)
    return img


def _scene(grid: np.ndarray, dst_quad, size=(960, 720), seed: int = 0):
    """Board warped into a cluttered scene; returns (frame, true playing-area corners)."""
    rng = np.random.default_rng(seed)
    w, h = size
    frame = np.full((h, w, 3), (120, 125, 130), dtype=np.uint8)
    for _ in range(25):  # non-blue clutter
        x, y = rng.integers(0, w - 40), rng.integers(0, h - 40)
        color = tuple(int(v) for v in rng.integers(0, 120, 3)) + ()
        cv2.rectangle(frame, (x, y), (x + 40, y + 30), (color[0], color[1] + 80, color[2]), -1)
    board = _render_board(grid)
    bh, bw = board.shape[:2]
    src = np.array([[0, 0], [bw, 0], [bw, bh], [0, bh]], dtype=np.float32)
    homography = cv2.getPerspectiveTransform(src, np.array(dst_quad, dtype=np.float32))
    warped = cv2.warpPerspective(board, homography, (w, h))
    mask = cv2.warpPerspective(np.full((bh, bw), 255, np.uint8), homography, (w, h))
    frame[mask > 0] = warped[mask > 0]
    play_area = np.array(
        [
            [[MARGIN, MARGIN], [MARGIN + COLS * PITCH, MARGIN]],
            [[MARGIN + COLS * PITCH, MARGIN + ROWS * PITCH], [MARGIN, MARGIN + ROWS * PITCH]],
        ],
        dtype=np.float32,
    ).reshape(1, 4, 2)
    truth = cv2.perspectiveTransform(play_area, homography)[0]
    return frame, truth


_QUADS = {
    "frontal": [[200, 120], [760, 120], [760, 650], [200, 650]],
    "tilted": [[230, 90], [770, 140], [740, 660], [180, 620]],
    "small-far": [[380, 250], [600, 260], [590, 470], [385, 465]],
}


@pytest.mark.parametrize("name", list(_QUADS))
def test_locate_board_finds_the_playing_area(name):
    grid = _sample_grid()
    frame, truth = _scene(grid, _QUADS[name])
    corners = locate_board(frame)
    assert corners is not None
    pitch = np.linalg.norm(truth[1] - truth[0]) / COLS
    assert np.abs(corners - truth).max() < 0.15 * pitch

    detector = BoardDetector()
    detector.set_corners(corners)
    detected, warped = detector.process_frame(frame)
    assert warped is not None
    np.testing.assert_array_equal(detected, grid)


def test_locate_board_rejects_scenes_without_a_full_board():
    empty_scene = np.full((480, 640, 3), (120, 125, 130), dtype=np.uint8)
    assert locate_board(empty_scene) is None

    frame, _ = _scene(_sample_grid(), _QUADS["frontal"])
    occluded = frame.copy()
    cv2.rectangle(occluded, (180, 100), (480, 680), (120, 125, 130), -1)  # left half hidden
    assert locate_board(occluded) is None

    blue_wall = np.full((480, 640, 3), _BLUE, dtype=np.uint8)
    assert locate_board(blue_wall) is None


def test_set_corners_is_click_order_independent():
    a, b = BoardDetector(), BoardDetector()
    corners = [[10, 10], [710, 12], [705, 610], [8, 605]]
    a.set_corners(corners)
    b.set_corners([corners[2], corners[0], corners[3], corners[1]])
    np.testing.assert_allclose(a.matrix, b.matrix)


# ------------------------------------------------------------ color adaptation
def _warped(grid: np.ndarray, detector: BoardDetector) -> np.ndarray:
    frame, truth = _scene(grid, _QUADS["frontal"])
    detector.set_corners(truth)
    _, warped = detector.process_frame(frame)
    assert warped is not None
    return warped


def _dim(img: np.ndarray, value: float = 0.25, saturation: float = 0.7) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] *= saturation
    hsv[..., 2] *= value
    return cv2.cvtColor(hsv.clip(0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)


def test_dim_light_breaks_defaults_and_adaptation_recovers():
    grid = _sample_grid()
    detector = BoardDetector()
    dim = _dim(_warped(grid, detector))
    assert not np.array_equal(detector.classify_board_image(dim), grid)

    assert detector.adapt_colors(dim, grid)
    np.testing.assert_array_equal(detector.classify_board_image(dim), grid)

    # The adapted profile generalizes to the next position in the same light.
    nxt = grid.copy()
    nxt[ROWS - 1, 1] = 2
    np.testing.assert_array_equal(detector.classify_board_image(_dim(_warped(nxt, detector))), nxt)


def test_adaptation_refuses_a_profile_that_contradicts_the_reading():
    grid = _sample_grid()
    detector = BoardDetector()
    warped = _warped(grid, detector)
    before = detector.colors
    wrong = grid.copy()
    wrong[ROWS - 1, 1] = 1  # claims a token in an empty hole
    assert not detector.adapt_colors(warped, wrong)
    assert detector.colors is before


def test_adaptation_needs_tokens():
    detector = BoardDetector()
    empty = np.zeros((ROWS, COLS), dtype=np.int8)
    assert not detector.adapt_colors(_warped(empty, detector), empty)


def test_red_hue_band_wraps_around_zero():
    low = _wrapped_hue_ranges(3.0, 8, 60, 50)
    assert [(int(lo[0]), int(hi[0])) for lo, hi in low] == [(0, 11), (175, 180)]
    high = _wrapped_hue_ranges(176.0, 8, 60, 50)
    assert [(int(lo[0]), int(hi[0])) for lo, hi in high] == [(168, 180), (0, 4)]
    assert len(_wrapped_hue_ranges(90.0, 8, 60, 50)) == 1


def test_profile_counts_pixels():
    hsv = np.zeros((4, 4, 3), dtype=np.uint8)
    hsv[:2] = (0, 200, 200)  # red
    hsv[2:] = (30, 200, 200)  # yellow
    assert ColorProfile().pixel_counts(hsv) == (8, 8)


# ------------------------------------------------------- real photo fixtures
def _photo_fixtures():
    if not FIXTURES.is_dir():
        return []
    return sorted(p for p in FIXTURES.glob("*.json"))


@pytest.mark.parametrize("label", _photo_fixtures(), ids=lambda p: p.stem)
def test_labelled_photo_fixtures(label):
    """Regression-test real webcam photos: ``tests/fixtures/vision/<name>.png``
    with ``<name>.json`` = ``{"grid": [[...6 rows of 7...]], "corners": optional
    [[x, y] x4]}``. Without ``corners`` the board must be found automatically.
    (Collected automatically; there are no photos in the repository yet.)"""
    spec = json.loads(label.read_text(encoding="utf-8"))
    frame = cv2.imread(str(label.with_suffix(".png")))
    assert frame is not None
    corners = spec.get("corners") or locate_board(frame)
    assert corners is not None, "board not found automatically"
    detector = BoardDetector()
    detector.set_corners(corners)
    grid, _ = detector.process_frame(frame)
    np.testing.assert_array_equal(grid, np.array(spec["grid"], dtype=np.int8))


# ------------------------------------------------- interactive calibration
class _SceneCapture:
    def __init__(self, frame: np.ndarray, frames: int = 5) -> None:
        self.frame = frame
        self.frames = frames

    def read(self):
        if self.frames <= 0:
            return False, None
        self.frames -= 1
        return True, self.frame.copy()


def _fake_window(monkeypatch, keys, clicks=()):
    import pefforza.vision.board_detector as bd

    key_iter = iter(keys)
    pending = list(clicks)
    callbacks = []
    monkeypatch.setattr(bd.cv2, "namedWindow", lambda *_a: None)
    monkeypatch.setattr(bd.cv2, "setMouseCallback", lambda _w, cb: callbacks.append(cb))
    monkeypatch.setattr(bd.cv2, "imshow", lambda *_a: None)
    monkeypatch.setattr(bd.cv2, "destroyWindow", lambda *_a: None)

    def wait_key(_ms):
        while pending:
            x, y = pending.pop(0)
            callbacks[0](cv2.EVENT_LBUTTONDOWN, x, y, 0, None)
        return next(key_iter, -1)

    monkeypatch.setattr(bd.cv2, "waitKey", wait_key)


def test_calibrate_accepts_the_detected_board_with_enter(monkeypatch):
    grid = _sample_grid()
    frame, _ = _scene(grid, _QUADS["tilted"])
    _fake_window(monkeypatch, keys=[-1, 13])
    detector = BoardDetector()
    assert detector.calibrate(_SceneCapture(frame))
    detected, _ = detector.process_frame(frame)
    np.testing.assert_array_equal(detected, grid)

    # Overlays render onto the frame once calibrated.
    canvas = frame.copy()
    detector.draw_overlays(canvas)
    detector.draw_move(canvas, 3)
    assert not np.array_equal(canvas, frame)


def test_calibrate_manual_clicks_and_abort(monkeypatch):
    grid = _sample_grid()
    frame, truth = _scene(grid, _QUADS["frontal"])
    clicks = [tuple(int(v) for v in pt) for pt in truth[[2, 0, 3, 1]]]
    _fake_window(monkeypatch, keys=[], clicks=clicks)
    detector = BoardDetector()
    assert detector.calibrate(_SceneCapture(frame), auto=False)
    detected, _ = detector.process_frame(frame)
    np.testing.assert_array_equal(detected, grid)

    _fake_window(monkeypatch, keys=[ord("q")])
    assert not BoardDetector().calibrate(_SceneCapture(frame), flip=True)
    _fake_window(monkeypatch, keys=[])
    assert not BoardDetector().calibrate(_SceneCapture(frame, frames=0))
