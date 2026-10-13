"""Headless tests for the board-image classifier.

We synthesize a "perfect" warped board image in code (blue grid + colored
circles) and assert ``BoardDetector.classify_board_image`` returns the
expected grid. No webcam, no calibration, no display required.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from pefforza.constants import COLS, ROWS
from pefforza.rules import empty_board
from pefforza.vision.board_detector import BoardDetector

# Convenience BGR colors matching the detector's HSV bands.
_BGR_BLUE = (200, 100, 30)
_BGR_RED = (40, 40, 220)
_BGR_YELLOW = (40, 220, 220)


def _synthetic_board(grid: NDArray[np.int8], width: int = 700, height: int = 600) -> np.ndarray:
    """Render a fake perspective-corrected board image for ``grid``.

    Grid encoding: 0=empty, 1=red, 2=yellow. Returns a BGR uint8 image.
    """
    width = (width // COLS) * COLS
    height = (height // ROWS) * ROWS
    cell_w = width // COLS
    cell_h = height // ROWS
    radius = int(min(cell_w, cell_h) * 0.40)

    img = np.full((height, width, 3), _BGR_BLUE, dtype=np.uint8)
    for r in range(ROWS):
        for c in range(COLS):
            cx = c * cell_w + cell_w // 2
            cy = r * cell_h + cell_h // 2
            v = int(grid[r, c])
            if v == 1:
                cv2.circle(img, (cx, cy), radius, _BGR_RED, -1)
            elif v == 2:
                cv2.circle(img, (cx, cy), radius, _BGR_YELLOW, -1)
            # else: empty — leave the blue square (cell hole would be black on
            # a real board, but blue is enough; the empty class is the default
            # when no color threshold is exceeded, which is also what blue
            # gives us here).
    return img


def test_empty_board_classified_as_empty():
    detector = BoardDetector()
    img = _synthetic_board(empty_board())
    grid = detector.classify_board_image(img)
    np.testing.assert_array_equal(grid, np.zeros((ROWS, COLS), dtype=np.int8))


def test_single_red_token_at_corner():
    detector = BoardDetector()
    expected = empty_board()
    expected[ROWS - 1, 0] = 1
    img = _synthetic_board(expected)
    grid = detector.classify_board_image(img)
    np.testing.assert_array_equal(grid, expected)


def test_single_yellow_token_at_corner():
    detector = BoardDetector()
    expected = empty_board()
    expected[0, COLS - 1] = 2
    img = _synthetic_board(expected)
    grid = detector.classify_board_image(img)
    np.testing.assert_array_equal(grid, expected)


def test_full_board_round_trip():
    """Place every legal token id in every cell and ensure perfect recovery."""
    detector = BoardDetector()
    expected = np.array(
        [
            [1, 2, 1, 2, 1, 2, 1],
            [2, 1, 2, 1, 2, 1, 2],
            [1, 2, 1, 2, 1, 2, 1],
            [2, 1, 2, 1, 2, 1, 2],
            [1, 2, 1, 2, 1, 2, 1],
            [2, 1, 2, 1, 2, 1, 2],
        ],
        dtype=np.int8,
    )
    img = _synthetic_board(expected)
    grid = detector.classify_board_image(img)
    np.testing.assert_array_equal(grid, expected)


def test_horizontal_line_red():
    detector = BoardDetector()
    expected = empty_board()
    expected[ROWS - 1, :4] = 1
    img = _synthetic_board(expected)
    grid = detector.classify_board_image(img)
    np.testing.assert_array_equal(grid, expected)


def test_diagonal_yellow():
    detector = BoardDetector()
    expected = empty_board()
    for i in range(4):
        expected[i + 1, i] = 2
    img = _synthetic_board(expected)
    grid = detector.classify_board_image(img)
    np.testing.assert_array_equal(grid, expected)


@pytest.mark.parametrize("dim", [(420, 360), (700, 600), (840, 720)])
def test_works_at_multiple_resolutions(dim):
    """The classifier must work at any size that's a multiple of (COLS, ROWS)."""
    width, height = dim
    detector = BoardDetector(width=width, height=height)
    expected = empty_board()
    expected[2, 3] = 1
    expected[3, 4] = 2
    img = _synthetic_board(expected, width=width, height=height)
    grid = detector.classify_board_image(img)
    np.testing.assert_array_equal(grid, expected)


def test_cell_confidences_high_for_token_low_for_empty():
    detector = BoardDetector()
    expected = empty_board()
    expected[ROWS - 1, 3] = 1
    img = _synthetic_board(expected)
    confidences = detector.cell_confidences(img)
    assert confidences[ROWS - 1, 3] > 0.5  # well-classified token
    # All other cells: low fill ratio.
    mask = np.ones_like(confidences, dtype=bool)
    mask[ROWS - 1, 3] = False
    assert confidences[mask].max() < 0.2


def test_grid_dtype_is_int8():
    detector = BoardDetector()
    img = _synthetic_board(empty_board())
    grid = detector.classify_board_image(img)
    assert grid.dtype == np.int8


def test_order_points_handles_any_click_order():
    """Regression for the 'numbers appear on the side' bug.

    Whatever order the user clicked the 4 corners, the calibration must end
    up oriented with TL at warped origin and TR along the warped top edge
    (so overlays land above the board, not beside it).
    """
    expected_tl = (10, 20)
    expected_tr = (300, 30)
    expected_br = (310, 250)
    expected_bl = (5, 240)
    canonical = [expected_tl, expected_tr, expected_br, expected_bl]

    permutations = [
        [expected_tl, expected_tr, expected_br, expected_bl],  # already correct
        [expected_tr, expected_br, expected_bl, expected_tl],  # rotated by 1
        [expected_br, expected_bl, expected_tl, expected_tr],  # rotated by 2
        [expected_bl, expected_tl, expected_tr, expected_br],  # rotated by 3
        [expected_tl, expected_bl, expected_br, expected_tr],  # reversed clockwise
    ]
    for perm in permutations:
        ordered = BoardDetector._order_points(perm)
        for got, want in zip(ordered, canonical, strict=True):
            assert tuple(int(v) for v in got) == want, f"perm={perm} ordered={ordered}"


def test_physical_col_is_identity_when_not_flipped():
    """Unflipped feed: display and physical columns share the same order."""
    detector = BoardDetector()
    detector.flipped = False
    assert detector.physical_col(0) == 0
    assert detector.physical_col(COLS - 1) == COLS - 1


def test_physical_col_is_mirrored_when_flipped():
    """Mirrored feed: display column 0 is the physical board's last column.

    Regression for the AR bug where the recommendation arrow was drawn on
    the flipped display frame using the physical (mirrored) column index,
    landing on the opposite side of the board from the announced column.
    """
    detector = BoardDetector()
    detector.flipped = True
    assert detector.physical_col(0) == COLS - 1
    assert detector.physical_col(COLS - 1) == 0
    assert detector.physical_col(COLS // 2) == COLS - 1 - (COLS // 2)


# ------------------------------------------- calibration-dependent helpers


def _calibrated_detector() -> BoardDetector:
    """Detector calibrated over a sub-rectangle of a larger camera frame.

    The overlay helpers map board-space points *above* the board (negative
    y) back into frame space, so the fixture needs the board offset inside
    the frame the way a real calibration would be.
    """
    detector = BoardDetector()
    x0, y0 = 150, 200
    frame_corners = np.array(
        [
            [x0, y0],
            [x0 + detector.width, y0],
            [x0 + detector.width, y0 + detector.height],
            [x0, y0 + detector.height],
        ],
        dtype=np.float32,
    )
    board_corners = np.array(
        [
            [0, 0],
            [detector.width, 0],
            [detector.width, detector.height],
            [0, detector.height],
        ],
        dtype=np.float32,
    )
    # calibrate() stores the frame -> board transform.
    detector.matrix = cv2.getPerspectiveTransform(frame_corners, board_corners)
    return detector


def _blank_frame(height: int = 900, width: int = 1000) -> np.ndarray:
    return np.zeros((height, width, 3), dtype=np.uint8)


def test_process_frame_before_calibration_returns_none():
    detector = BoardDetector()
    assert detector.process_frame(_blank_frame()) == (None, None)


def test_process_frame_warps_and_classifies():
    detector = _calibrated_detector()
    grid, warped = detector.process_frame(_blank_frame())
    assert grid.shape == (ROWS, COLS)
    assert grid.dtype == np.int8
    assert warped.shape == (detector.height, detector.width, 3)


def test_draw_overlays_and_move_are_noops_before_calibration():
    detector = BoardDetector()
    frame = _blank_frame()
    detector.draw_overlays(frame)
    detector.draw_move(frame, col=3)
    assert not frame.any()


def test_draw_overlays_and_move_annotate_when_calibrated():
    detector = _calibrated_detector()
    frame = _blank_frame()
    detector.draw_overlays(frame)
    assert frame.any()  # column numbers were drawn
    frame2 = _blank_frame()
    detector.draw_move(frame2, col=3)
    assert frame2.any()  # arrow was drawn


def test_transform_points_maps_board_coords_back_to_frame():
    detector = _calibrated_detector()
    board_pts = [(100, -50), (350, -20)]
    mapped = detector._transform_points(board_pts)
    assert len(mapped) == 2
    for (x, y), (mx, my) in zip(board_pts, mapped, strict=True):
        assert isinstance(mx, int) and isinstance(my, int)
        # Inverse of the frame->board homography: the board point lands at
        # the same offset inside the frame's board rectangle.
        assert (mx, my) == (x + 150, y + 200)
