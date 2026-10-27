"""Webcam-based Connect 4 board detector.

The detector takes a perspective-corrected crop of the physical board and
classifies each cell as empty / red / yellow using HSV color thresholds.

Two steps that used to be manual are automatic:

* **board localization** - :func:`locate_board` finds the 6x7 lattice of
  holes in the blue frame and returns the four corners of the playing area,
  so calibration is a single key press (clicking the corners still works);
* **color adaptation** - :meth:`BoardDetector.adapt_colors` re-fits the HSV
  thresholds to the current lighting from a board state the validator has
  already accepted, and only commits the new profile if it reproduces that
  state exactly.

Color convention is: ``1 = Red``, ``2 = Yellow`` (vision view). Translate to
the model's perspective with :func:`pefforza.rules.swap_perspective` if the AI
is playing yellow.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from pefforza.constants import COLS, ROWS

HsvRange = tuple[NDArray[Any], NDArray[Any]]

# HSV color thresholds. Tunable via ColorProfile; the defaults match a typical
# indoor lighting setup. Red wraps around the H axis so we keep two ranges.
_DEFAULT_RED_RANGES: tuple[HsvRange, ...] = (
    (np.array([0, 70, 70]), np.array([12, 255, 255])),
    (np.array([165, 70, 70]), np.array([180, 255, 255])),
)
_DEFAULT_YELLOW_RANGE: HsvRange = (np.array([18, 70, 70]), np.array([45, 255, 255]))

# Fraction of cell pixels that must match a color to count as occupied.
_FILL_THRESHOLD = 0.30
# Inset applied to each cell ROI to ignore frame edges.
_CELL_MARGIN_FRAC = 0.20

# Board frame color for automatic localization (typical blue Connect 4 frame).
_BOARD_BLUE_RANGE: HsvRange = (np.array([90, 80, 40]), np.array([135, 255, 255]))

# Bounds used when re-fitting thresholds to the observed tokens.
_MIN_HUE_HALF_WIDTH = 6
_MAX_HUE_HALF_WIDTH = 20
_MIN_SV_FLOOR = 40
_MAX_SV_FLOOR = 160
# Pixels this unsaturated inside a token cell are glare or edges, not token.
_TOKEN_PIXEL_MIN_SAT = 50
_MIN_TOKEN_PIXELS = 20


@dataclass
class ColorProfile:
    """HSV thresholds used to classify cells (OpenCV hue scale 0-180)."""

    red_ranges: tuple[HsvRange, ...] = field(default_factory=lambda: _DEFAULT_RED_RANGES)
    yellow_range: HsvRange = field(default_factory=lambda: _DEFAULT_YELLOW_RANGE)
    fill_threshold: float = _FILL_THRESHOLD

    def pixel_counts(self, roi_hsv: NDArray[Any]) -> tuple[int, int]:
        """Number of red and yellow pixels in an HSV region."""
        red = sum(
            int(cv2.countNonZero(cv2.inRange(roi_hsv, low, high))) for low, high in self.red_ranges
        )
        yellow = int(cv2.countNonZero(cv2.inRange(roi_hsv, *self.yellow_range)))
        return red, yellow


class BoardDetector:
    """Detects a 6x7 Connect 4 board from a calibrated webcam feed."""

    def __init__(
        self, width: int = 700, height: int = 600, colors: ColorProfile | None = None
    ) -> None:
        # Pick warp dimensions divisible by COLS x ROWS so cell sizes are exact.
        self.width = (width // COLS) * COLS
        self.height = (height // ROWS) * ROWS
        self.rows = ROWS
        self.cols = COLS
        self.colors = colors if colors is not None else ColorProfile()

        self.points: list[tuple[int, int]] = []
        self.matrix: NDArray[Any] | None = None
        # Set by calibrate(): True when the display feed is mirrored, which
        # reverses the left-to-right mapping between display and physical
        # columns (see physical_col).
        self.flipped: bool = False

    # ------------------------------------------------------------ Calibration
    def calibrate(self, cap: cv2.VideoCapture, flip: bool = False, auto: bool = True) -> bool:
        """Calibrate the board corners from the live feed.

        With ``auto`` (the default) the board is located automatically on
        every frame and outlined; press ENTER (or 'a') to accept it. Clicking
        the 4 corners (any order) always works as a manual override.

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

        detected: NDArray[np.float32] | None = None
        try:
            while len(self.points) < 4:
                ret, frame = cap.read()
                if not ret:
                    return False
                if flip:
                    frame = cv2.flip(frame, 1)
                display = frame.copy()
                if auto:
                    detected = locate_board(frame)
                    if detected is not None:
                        poly = detected.astype(np.int32).reshape(-1, 1, 2)
                        cv2.polylines(display, [poly], True, (0, 255, 0), 2)
                    hint = (
                        "Board found: ENTER to accept, or click 4 corners"
                        if detected is not None
                        else "Searching for the board... or click 4 corners"
                    )
                    cv2.putText(
                        display, hint, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
                    )
                for pt in self.points:
                    cv2.circle(display, pt, 5, (0, 255, 0), -1)
                cv2.imshow(window, display)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    return False
                if detected is not None and key in (13, 10, ord("a")):
                    self.set_corners(detected)
                    return True
        finally:
            cv2.destroyWindow(window)

        self.set_corners(self.points)
        return True

    def set_corners(self, points: Sequence[Sequence[float]] | NDArray[Any]) -> None:
        """Set the playing-area corners (any order) and compute the warp.

        Corners are ordered canonically so the warp orientation is
        independent of click order; otherwise overlays end up rotated.
        """
        pts1 = self._order_points(points)
        pts2 = np.array(
            [[0, 0], [self.width, 0], [self.width, self.height], [0, self.height]],
            dtype=np.float32,
        )
        self.matrix = cv2.getPerspectiveTransform(pts1, pts2)

    def _click_event(self, event, x, y, flags, param) -> None:  # noqa: ARG002
        if event == cv2.EVENT_LBUTTONDOWN and len(self.points) < 4:
            self.points.append((int(x), int(y)))

    @staticmethod
    def _order_points(points: Sequence[Sequence[float]] | NDArray[Any]) -> NDArray[np.float32]:
        """Sort points into canonical [TL, TR, BR, BL] regardless of click order.

        Uses the standard sum/diff trick:
        * Top-left has the smallest ``x + y``
        * Bottom-right has the largest ``x + y``
        * Top-right has the smallest ``y - x``
        * Bottom-left has the largest ``y - x``

        This makes calibration tolerant of users who click corners in any
        rotation: the resulting perspective warp always orients with the
        physical top edge as warped ``y=0``, so column-number overlays and
        AR arrows always appear above the board, never on the side. With
        more than four points it returns the four extreme ones.
        """
        pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
        s = pts.sum(axis=1)
        diff = pts[:, 1] - pts[:, 0]
        tl = pts[int(np.argmin(s))]
        br = pts[int(np.argmax(s))]
        tr = pts[int(np.argmin(diff))]
        bl = pts[int(np.argmax(diff))]
        return np.array([tl, tr, br, bl], dtype=np.float32)

    # --------------------------------------------------------- Frame analysis
    def _cell_rois(self, hsv: NDArray[Any]) -> Iterator[tuple[int, int, NDArray[Any]]]:
        """Yield ``(row, col, roi)`` for the inset region of every cell."""
        cell_w = self.width // self.cols
        cell_h = self.height // self.rows
        margin = int(min(cell_w, cell_h) * _CELL_MARGIN_FRAC)
        for r in range(self.rows):
            for c in range(self.cols):
                roi = hsv[
                    r * cell_h + margin : (r + 1) * cell_h - margin,
                    c * cell_w + margin : (c + 1) * cell_w - margin,
                ]
                yield r, c, roi

    def classify_board_image(self, board_img: NDArray[Any]) -> NDArray[np.int8]:
        """Classify each cell of an already-warped board image.

        ``board_img`` must be a BGR image of size ``(self.height, self.width)``.
        Returns a ``(ROWS, COLS)`` int8 grid with ``0=empty, 1=red, 2=yellow``.

        Useful for unit tests (synthetic board images) and for diagnosing live
        feeds without going through ``calibrate()``.
        """
        hsv = cv2.cvtColor(board_img, cv2.COLOR_BGR2HSV)
        grid = np.zeros((self.rows, self.cols), dtype=np.int8)
        for r, c, roi in self._cell_rois(hsv):
            if roi.size:
                grid[r, c] = self._classify_cell(roi)
        return grid

    def cell_confidences(self, board_img: NDArray[Any]) -> NDArray[np.float32]:
        """Per-cell fill ratio of the detected color in [0,1].

        Returns a (ROWS, COLS) array. Useful to spot cells classified at low
        confidence so you can adjust thresholds or lighting.
        """
        hsv = cv2.cvtColor(board_img, cv2.COLOR_BGR2HSV)
        out = np.zeros((self.rows, self.cols), dtype=np.float32)
        for r, c, roi in self._cell_rois(hsv):
            if roi.size:
                red, yellow = self.colors.pixel_counts(roi)
                out[r, c] = max(red, yellow) / (roi.shape[0] * roi.shape[1])
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
        red_pixels, yellow_pixels = self.colors.pixel_counts(roi)
        threshold = total * self.colors.fill_threshold
        if red_pixels >= threshold and red_pixels >= yellow_pixels:
            return 1
        if yellow_pixels >= threshold:
            return 2
        return 0

    def adapt_colors(self, board_img: NDArray[Any], grid: NDArray[np.integer]) -> bool:
        """Re-fit the color thresholds to ``board_img`` given its true ``grid``.

        ``grid`` must be a state the caller trusts (accepted by
        :class:`~pefforza.vision.validation.BoardStateValidator`). For each
        token color present on the board, the hue band is re-centered on the
        observed token pixels and the saturation/value floors follow the
        observed lighting. The candidate profile is committed only if it
        classifies ``board_img`` exactly as ``grid`` - adaptation can sharpen
        the detector but never break the current reading. Returns True if
        the profile changed.
        """
        hsv = cv2.cvtColor(board_img, cv2.COLOR_BGR2HSV)
        samples: dict[int, list[NDArray[Any]]] = {1: [], 2: []}
        for r, c, roi in self._cell_rois(hsv):
            label = int(grid[r, c])
            if label in samples and roi.size:
                pixels = roi.reshape(-1, 3)
                samples[label].append(pixels[pixels[:, 1] >= _TOKEN_PIXEL_MIN_SAT])

        candidate = ColorProfile(
            red_ranges=self.colors.red_ranges,
            yellow_range=self.colors.yellow_range,
            fill_threshold=self.colors.fill_threshold,
        )
        changed = False
        for label, chunks in samples.items():
            if not chunks:
                continue
            pixels = np.concatenate(chunks)
            if len(pixels) < _MIN_TOKEN_PIXELS:
                continue
            center, half = _hue_band(pixels[:, 0].astype(np.float64), circular=label == 1)
            s_floor = _sv_floor(pixels[:, 1])
            v_floor = _sv_floor(pixels[:, 2])
            if label == 1:
                candidate.red_ranges = _wrapped_hue_ranges(center, half, s_floor, v_floor)
            else:
                lo, hi = max(0, round(center - half)), min(180, round(center + half))
                candidate.yellow_range = (
                    np.array([lo, s_floor, v_floor]),
                    np.array([hi, 255, 255]),
                )
            changed = True
        if not changed:
            return False

        trial = BoardDetector(self.width, self.height, colors=candidate)
        if not np.array_equal(trial.classify_board_image(board_img), np.asarray(grid)):
            return False
        self.colors = candidate
        return True

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


# ------------------------------------------------------------------ helpers
def _sv_floor(values: NDArray[Any]) -> int:
    """Saturation/value floor just below the dimmest typical token pixel."""
    return int(np.clip(np.percentile(values, 5) - 15, _MIN_SV_FLOOR, _MAX_SV_FLOOR))


def _hue_band(hues: NDArray[np.float64], *, circular: bool) -> tuple[float, int]:
    """Robust center and half-width of a hue sample (OpenCV scale 0-180)."""
    if circular:
        angles = hues * (np.pi / 90.0)
        mean_angle = np.arctan2(np.sin(angles).mean(), np.cos(angles).mean())
        center = float(np.degrees(mean_angle) / 2.0) % 180.0
        dist = np.abs((hues - center + 90.0) % 180.0 - 90.0)
    else:
        center = float(np.median(hues))
        dist = np.abs(hues - center)
    half = int(np.clip(np.percentile(dist, 95) + 4, _MIN_HUE_HALF_WIDTH, _MAX_HUE_HALF_WIDTH))
    return center, half


def _wrapped_hue_ranges(
    center: float, half: int, s_floor: int, v_floor: int
) -> tuple[HsvRange, ...]:
    """Red hue band around ``center``, split in two where it wraps past 0/180."""
    lo, hi = center - half, center + half

    def band(a: float, b: float) -> HsvRange:
        return np.array([round(a), s_floor, v_floor]), np.array([round(b), 255, 255])

    if lo < 0:
        return band(0, hi), band(180 + lo, 180)
    if hi > 180:
        return band(lo, 180), band(0, hi - 180)
    return (band(lo, hi),)


def locate_board(
    frame: NDArray[Any], blue_range: HsvRange = _BOARD_BLUE_RANGE
) -> NDArray[np.float32] | None:
    """Find the playing area of a blue 6x7 board in a BGR ``frame``.

    The holes of the frame (empty or holding a token) are the non-blue
    blobs enclosed by the board's blue outline. Their centers form a 6x7
    lattice; the lattice spanned by the four corner holes, extended by half
    a cell, gives the corners of the playing area - independent of how wide
    the frame's margins or stand are. Returns ``[TL, TR, BR, BL]`` corners,
    or None if no board is confidently found (the lattice must explain the
    detected holes); callers then fall back to manual corner clicks.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, *blue_range)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None or not contours:
        return None
    links = hierarchy[0]

    outer = [i for i, link in enumerate(links) if link[3] == -1]
    board_idx = max(outer, key=lambda i: cv2.contourArea(contours[i]))
    board_area = cv2.contourArea(contours[board_idx])
    if board_area < 0.03 * frame.shape[0] * frame.shape[1]:
        return None

    # Holes: round children of the board outline, no larger than a cell.
    centers: list[tuple[float, float]] = []
    areas: list[float] = []
    for i, link in enumerate(links):
        if link[3] != board_idx:
            continue
        area = cv2.contourArea(contours[i])
        perimeter = cv2.arcLength(contours[i], True)
        if not (board_area / 400 < area < board_area / (ROWS * COLS)) or perimeter == 0:
            continue
        if 4 * np.pi * area / perimeter**2 < 0.6:
            continue
        m = cv2.moments(contours[i])
        centers.append((m["m10"] / m["m00"], m["m01"] / m["m00"]))
        areas.append(area)
    min_holes = int(0.85 * ROWS * COLS)
    if len(centers) < min_holes:
        return None
    sizes = np.array(areas)
    typical = sizes[np.abs(sizes - np.median(sizes)) < 0.6 * np.median(sizes)]
    pts = np.array(centers, dtype=np.float32)[np.isin(sizes, typical)]
    if len(pts) < min_holes:
        return None

    corner_holes = BoardDetector._order_points(pts)
    ideal = np.array(
        [[0.5, 0.5], [COLS - 0.5, 0.5], [COLS - 0.5, ROWS - 0.5], [0.5, ROWS - 0.5]],
        dtype=np.float32,
    )
    lattice = cv2.getPerspectiveTransform(ideal, corner_holes)

    # Verify: the lattice must predict the detected holes (rejects clutter
    # and partial boards that merely happen to have four extreme blobs).
    grid_pts = np.array(
        [[[c + 0.5, r + 0.5] for r in range(ROWS) for c in range(COLS)]], dtype=np.float32
    )
    predicted = cv2.perspectiveTransform(grid_pts, lattice)[0]
    pitch = float(np.linalg.norm(corner_holes[1] - corner_holes[0])) / (COLS - 1)
    dists = np.linalg.norm(predicted[:, None, :] - pts[None, :, :], axis=2)
    tolerance = 0.3 * pitch
    if (dists.min(axis=1) < tolerance).sum() < min_holes or (dists.min(axis=0) >= tolerance).any():
        return None

    corners = np.array([[[0, 0], [COLS, 0], [COLS, ROWS], [0, ROWS]]], dtype=np.float32)
    return cv2.perspectiveTransform(corners, lattice)[0].astype(np.float32)
