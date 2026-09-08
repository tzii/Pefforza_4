"""Headless tests for the live vision diagnostic helpers.

``pefforza.vision.diagnose`` is a webcam tool, but its annotation and
argument-parsing helpers are pure image/array logic and pin the overlay
contract used by the on-screen debug view. No camera required.
"""

from __future__ import annotations

import numpy as np

from pefforza.constants import COLS, ROWS
from pefforza.vision.diagnose import _annotate, _parse_args


def _blank_board() -> np.ndarray:
    return np.zeros((600, 700, 3), dtype=np.uint8)


def test_annotate_returns_modified_copy_same_shape():
    board_img = _blank_board()
    grid = np.zeros((ROWS, COLS), dtype=np.int8)
    confidences = np.zeros((ROWS, COLS), dtype=np.float32)

    annotated = _annotate(
        board_img, grid, confidences, width=board_img.shape[1], height=board_img.shape[0]
    )

    assert annotated.shape == board_img.shape
    assert annotated.dtype == np.uint8
    # Labels were drawn onto the copy; the input frame is untouched.
    assert annotated is not board_img
    assert annotated.any()
    assert not board_img.any()


def test_annotate_handles_all_token_values():
    """Red, yellow, and empty cells must all render without error."""
    board_img = _blank_board()
    grid = np.zeros((ROWS, COLS), dtype=np.int8)
    grid[ROWS - 1, 0] = 1  # red
    grid[ROWS - 1, 1] = 2  # yellow
    confidences = np.full((ROWS, COLS), 0.5, dtype=np.float32)

    annotated = _annotate(
        board_img, grid, confidences, width=board_img.shape[1], height=board_img.shape[0]
    )
    assert annotated.shape == board_img.shape


def test_parse_args_defaults():
    args = _parse_args([])
    assert args.camera == 0
    assert args.flip is False
