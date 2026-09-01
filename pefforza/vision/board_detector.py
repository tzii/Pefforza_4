"""Webcam-based Connect 4 board detector.

The detector takes a perspective-corrected crop of the physical board and
classifies each cell as empty / red / yellow using HSV color thresholds.

Color convention is: ``1 = Red``, ``2 = Yellow`` (vision view). Translate to
the model's perspective with :func:`pefforza.rules.swap_perspective` if the AI
is playing yellow.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from pefforza.constants import COLS, ROWS

# HSV color thresholds. Tunable via constructor; the defaults match a typical
# indoor lighting setup. Red wraps around the H axis so we keep two ranges.
_DEFAULT_RED_RANGES = (
    (np.array([0, 70, 70]), np.array([12, 255, 255])),
    (np.array([165, 70, 70]), np.array([180, 255, 255])),
)
_DEFAULT_YELLOW_RANGE = (np.array([18, 70, 70]), np.array([45, 255, 255]))

# Fraction of cell pixels that must match a color to count as occupied.
_FILL_THRESHOLD = 0.30
# Inset applied to each cell ROI to ignore frame edges.
_CELL_MARGIN_FRAC = 0.20


class BoardDetector:
    """Detects a 6x7 Connect 4 board from a calibrated webcam feed."""

    def __init__(self, width: int = 700, height: int = 600) -> None:
        # Pick warp dimensions divisible by COLS x ROWS so cell sizes are exact.
        self.width = (width // COLS) * COLS
        self.height = (height // ROWS) * ROWS
        self.rows = ROWS
        self.cols = COLS

        self.points: list[tuple[int, int]] = []
        self.matrix: NDArray[Any] | None = None
        # Set by calibrate(): True when the display feed is mirrored, which
        # reverses the left-to-right mapping between display and physical
        # columns (see physical_col).
        self.flipped: bool = False

    # ------------------------------------------------------------ Calibration
    def calibrate(self, cap: cv2.VideoCapture, flip: bool = False) -> bool:
        """Open a window and let the user click the 4 corners (TL, TR, BR, BL).

        Returns True on success, False if the user pressed 'q' or the camera
        feed is unavailable. ``flip`` is remembered on the detector: it drives
        the display-to-physical column mapping used by :meth:`physical_col`
        and the numbering drawn by :meth:`draw_overlays`.
        """
        # Always start from a clean slate so re-calibration works.
        self.points = []
        self.matrix = None
        self.flipped = flip

        window = "Calibrate"
        cv2.namedWindow(window)
        # Bind the mouse callback once instead of per-frame.
        cv2.setMouseCallback(window, self._click_event)

        try:
            while len(self.points) < 4:
                ret, frame = cap.read()
                if not ret:
                    cv2.destroyWindow(window)
                    return False
                if flip:
                    frame = cv2.flip(frame, 1)
                for pt in self.points:
                    cv2.circle(frame, pt, 5, (0, 255, 0), -1)
                cv2.imshow(window, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    cv2.destroyWindow(window)
                    return False
        finally:
            cv2.destroyWindow(window)

        if len(self.points) != 4:
            return False

        # Order corners canonically so the warp orientation is independent of
        # the user's click order. Otherwise overlays end up rotated 90 / 180.
        pts1 = self._order_points(self.points)
        pts2 = np.array(
            [[0, 0], [self.width, 0], [self.width, self.height], [0, self.height]],
            dtype=np.float32,
        )
        self.matrix = cv2.getPerspectiveTransform(pts1, pts2)
        return True

    def _click_event(self, event, x, y, flags, param) -> None:  # noqa: ARG002
        if event == cv2.EVENT_LBUTTONDOWN and len(self.points) < 4:
            self.points.append((int(x), int(y)))

    @staticmethod
    def _order_points(points: list[tuple[int, int]]) -> NDArray[np.float32]:
        """Sort 4 points into canonical [TL, TR, BR, BL] regardless of click order.

        Uses the standard sum/diff trick:
        * Top-left has the smallest ``x + y``
        * Bottom-right has the largest ``x + y``
        * Top-right has the smallest ``y - x``
        * Bottom-left has the largest ``y - x``

        This makes calibration tolerant of users who click corners in any
        rotation: the resulting perspective warp always orients with the
        physical top edge as warped ``y=0``, so column-number overlays and
        AR arrows always appear above the board, never on the side.
        """
        pts = np.array(points, dtype=np.float32)
        s = pts.sum(axis=1)
        diff = pts[:, 1] - pts[:, 0]
        tl = pts[int(np.argmin(s))]
        br = pts[int(np.argmax(s))]
        tr = pts[int(np.argmin(diff))]
        bl = pts[int(np.argmax(diff))]
        return np.array([tl, tr, br, bl], dtype=np.float32)

    # --------------------------------------------------------- Frame analysis
    def classify_board_image(self, board_img: NDArray[Any]) -> NDArray[np.int8]:
        """Classify each cell of an already-warped board image.

        ``board_img`` must be a BGR image of size ``(self.height, self.width)``.
        Returns a ``(ROWS, COLS)`` int8 grid with ``0=empty, 1=red, 2=yellow``.

        Useful for unit tests (synthetic board images) and for diagnosing live
        feeds without going through ``calibrate()``.
        """
        hsv = cv2.cvtColor(board_img, cv2.COLOR_BGR2HSV)
        cell_w = self.width // self.cols
        cell_h = self.height // self.rows
        margin = int(min(cell_w, cell_h) * _CELL_MARGIN_FRAC)

        grid = np.zeros((self.rows, self.cols), dtype=np.int8)
        for r in range(self.rows):
            for c in range(self.cols):
                x1 = c * cell_w + margin
                y1 = r * cell_h + margin
                x2 = (c + 1) * cell_w - margin
                y2 = (r + 1) * cell_h - margin
                roi = hsv[y1:y2, x1:x2]
                if roi.size == 0:
                    continue
                grid[r, c] = self._classify_cell(roi)
        return grid

    def cell_confidences(self, board_img: NDArray[Any]) -> NDArray[np.float32]:
        """Per-cell fill ratio of the detected color in [0,1].

        Returns a (ROWS, COLS) array. Useful to spot cells classified at low
        confidence so you can adjust thresholds or lighting.
        """
        hsv = cv2.cvtColor(board_img, cv2.COLOR_BGR2HSV)
        cell_w = self.width // self.cols
        cell_h = self.height // self.rows
        margin = int(min(cell_w, cell_h) * _CELL_MARGIN_FRAC)

        out = np.zeros((self.rows, self.cols), dtype=np.float32)
        for r in range(self.rows):
            for c in range(self.cols):
                x1 = c * cell_w + margin
                y1 = r * cell_h + margin
                x2 = (c + 1) * cell_w - margin
                y2 = (r + 1) * cell_h - margin
                roi = hsv[y1:y2, x1:x2]
                if roi.size == 0:
                    continue
                total = roi.shape[0] * roi.shape[1]
                red = sum(
                    int(cv2.countNonZero(cv2.inRange(roi, low, high)))
                    for low, high in _DEFAULT_RED_RANGES
                )
                yellow = int(cv2.countNonZero(cv2.inRange(roi, *_DEFAULT_YELLOW_RANGE)))
                out[r, c] = max(red, yellow) / total
        return out

    def process_frame(
        self, frame: NDArray[Any]
    ) -> tuple[NDArray[np.int8] | None, NDArray[Any] | None]:
        """Return ``(grid, warped)`` for ``frame`` or ``(None, None)``.

        ``grid`` uses ``0=empty, 1=red, 2=yellow``. ``warped`` is the
        perspective-corrected BGR image (uint8 at runtime).
        """
        if self.matrix is None:
            return None, None

        # cv2 stubs return a loose ndarray; the runtime dtype is uint8 here.
        board_img = cv2.warpPerspective(frame, self.matrix, (self.width, self.height))
        grid = self.classify_board_image(board_img)
        return grid, board_img

    def _classify_cell(self, roi: NDArray[Any]) -> int:
        total = roi.shape[0] * roi.shape[1]
        if total == 0:
            return 0
        red_pixels = sum(
            int(cv2.countNonZero(cv2.inRange(roi, low, high))) for low, high in _DEFAULT_RED_RANGES
        )
        yellow_pixels = int(cv2.countNonZero(cv2.inRange(roi, *_DEFAULT_YELLOW_RANGE)))
        threshold = total * _FILL_THRESHOLD
        if red_pixels >= threshold and red_pixels >= yellow_pixels:
            return 1
        if yellow_pixels >= threshold:
            return 2
        return 0

    # -------------------------------------------------------------- Overlays
    def physical_col(self, display_col: int) -> int:
        """Map a display-frame column (0-indexed) to the physical board column.

        With a mirrored feed (``calibrate(flip=True)``) the display's
        left-to-right order is reversed relative to the physical board, so
        display column 0 is physical column ``cols - 1``. Without flipping,
        the two frames share the same order and the mapping is the identity.
        """
        return (self.cols - 1 - display_col) if self.flipped else display_col

    def _transform_points(self, points: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
        if self.matrix is None:
            return []
        pts_array = np.array([list(points)], dtype=np.float32)
        inv_matrix = np.linalg.inv(self.matrix)
        pts_original = cv2.perspectiveTransform(pts_array, inv_matrix)
        return [(int(p[0]), int(p[1])) for p in pts_original[0]]

    def draw_overlays(self, frame: NDArray[Any]) -> None:
        """Draw physical column numbers above the calibrated board area.

        Numbers use the physical board's left-to-right order, so with a
        mirrored feed they run right-to-left on screen and always match the
        column a human should play on the real board.
        """
        if self.matrix is None:
            return
        cell_w = self.width // self.cols
        targets = [(int((c + 0.5) * cell_w), -50) for c in range(self.cols)]
        for i, pt in enumerate(self._transform_points(targets)):
            text = str(self.physical_col(i) + 1)
            (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            tx, ty = pt[0] - w // 2, pt[1] + h // 2
            cv2.putText(frame, text, (tx + 1, ty + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
            cv2.putText(frame, text, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

    def draw_move(self, frame: NDArray[Any], col: int) -> None:
        """Draw an arrow pointing into display-frame column ``col`` (0-indexed).

        ``col`` lives in the same flipped/unflipped space the board was
        calibrated in, so it lines up with the classified grid by
        construction. Use :meth:`physical_col` to translate it before telling
        the user which column to play on the physical board.
        """
        if self.matrix is None:
            return
        cell_w = self.width // self.cols
        cx = int((col + 0.5) * cell_w)
        transformed = self._transform_points([(cx, -120), (cx, -20)])
        if len(transformed) < 2:
            return
        p1, p2 = transformed
        cv2.arrowedLine(frame, p1, p2, (255, 0, 255), 5, tipLength=0.3)
        cv2.circle(frame, p1, 10, (255, 0, 255), -1)
