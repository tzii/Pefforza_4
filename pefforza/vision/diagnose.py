"""Live vision diagnostic tool.

Run after calibrating the board to see exactly what the detector sees on
your webcam in real time. Each detected cell is annotated with the inferred
token (X = red, O = yellow, "." = empty) and a confidence value 0..1.

Usage:

.. code-block:: bash

    python -m pefforza.vision.diagnose             # default camera 0
    python -m pefforza.vision.diagnose --camera 1
    python -m pefforza.vision.diagnose --flip      # mirror webcam first

Controls:
    [SPACE]  pause / resume the stream
    [s]      save the current warped board to vision_debug.png
    [q]      quit
"""

from __future__ import annotations

import argparse
import logging
import sys

import cv2
import numpy as np

from pefforza.constants import COLS, ROWS
from pefforza.vision.board_detector import BoardDetector

logger = logging.getLogger(__name__)


def _annotate(
    board_img: np.ndarray,
    grid: np.ndarray,
    confidences: np.ndarray,
    width: int,
    height: int,
) -> np.ndarray:
    """Draw cell labels + confidence overlays onto a copy of ``board_img``."""
    annotated = board_img.copy()
    cell_w = width // COLS
    cell_h = height // ROWS
    for r in range(ROWS):
        for c in range(COLS):
            v = int(grid[r, c])
            conf = float(confidences[r, c])
            label = "X" if v == 1 else "O" if v == 2 else "."
            color = (0, 0, 255) if v == 1 else (0, 255, 255) if v == 2 else (200, 200, 200)
            cx = c * cell_w + cell_w // 2
            cy = r * cell_h + cell_h // 2
            cv2.putText(
                annotated,
                label,
                (cx - 12, cy + 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 0),
                4,
            )
            cv2.putText(
                annotated,
                label,
                (cx - 12, cy + 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                color,
                2,
            )
            cv2.putText(
                annotated,
                f"{conf:.2f}",
                (c * cell_w + 5, (r + 1) * cell_h - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
            )
    return annotated


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live board-detection diagnostic.")
    p.add_argument("--camera", type=int, default=0, help="cv2.VideoCapture index.")
    p.add_argument("--flip", action="store_true", help="Horizontally flip the webcam feed.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args(argv)

    cap = cv2.VideoCapture(args.camera)
    try:
        if not cap.isOpened():
            logger.error("Could not open webcam at index %d.", args.camera)
            return 2
        detector = BoardDetector()
        logger.info("Calibrate by clicking the 4 corners (TL, TR, BR, BL). 'q' aborts.")
        if not detector.calibrate(cap, flip=args.flip):
            logger.error("Calibration cancelled.")
            return 1

        logger.info("Running. SPACE = pause, s = save, q = quit.")
        last_grid: np.ndarray | None = None
        last_warped: np.ndarray | None = None
        paused = False
        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    logger.error("Camera read failed.")
                    break
                if args.flip:
                    frame = cv2.flip(frame, 1)
                grid, warped = detector.process_frame(frame)
                if grid is not None and warped is not None:
                    confidences = detector.cell_confidences(warped)
                    last_grid = grid
                    last_warped = warped
                    annotated = _annotate(
                        warped, grid, confidences, detector.width, detector.height
                    )
                    cv2.imshow("Vision Diagnose - Detected Board", annotated)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord(" "):
                paused = not paused
                logger.info("Paused." if paused else "Resumed.")
            if key == ord("s") and last_warped is not None and last_grid is not None:
                try:
                    saved = cv2.imwrite("vision_debug.png", last_warped)
                except cv2.error as exc:
                    logger.error("Could not save vision_debug.png: %s", exc)
                else:
                    if saved:
                        logger.info("Saved warped board to vision_debug.png")
                        logger.info("Detected grid:\n%s", last_grid)
                    else:
                        logger.error("Could not save vision_debug.png; check write permissions.")
    finally:
        cap.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
