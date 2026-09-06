"""Live AR Connect 4 assistant (default: AI plays Yellow, human Red).

Watches the webcam, detects the board state, and announces / draws the AI's
recommended move whenever it's the AI's turn.
Press 'r' to reset board tracking, or 'q' to quit.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import cv2
import numpy as np

from pefforza.constants import DEFAULT_MODEL_PATH
from pefforza.interaction.voice import VoiceEngine
from pefforza.rules import available_columns, check_winner, player_to_move, swap_perspective
from pefforza.vision.board_detector import BoardDetector
from pefforza.vision.validation import BoardStateValidator

logger = logging.getLogger(__name__)

try:
    from stable_baselines3 import PPO  # type: ignore
except Exception:  # pragma: no cover
    PPO = None  # type: ignore[assignment]

# Vision palette: 1 = Red, 2 = Yellow.
_AI_YELLOW = 2


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AR Connect 4 assistant.")
    p.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    p.add_argument("--camera", type=int, default=0, help="cv2.VideoCapture index.")
    p.add_argument("--no-voice", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    args = _parse_args(argv)

    voice = None if args.no_voice else VoiceEngine()
    detector = BoardDetector()

    model = None
    if PPO is None:
        logger.warning("stable-baselines3 not installed; using random actions.")
    elif args.model.exists():
        try:
            model = PPO.load(str(args.model))
            logger.info("Model loaded from %s", args.model)
        except Exception as exc:
            logger.warning("Could not load model %s: %s", args.model, exc)
    else:
        logger.warning("Model not found at %s; using random actions.", args.model)

    cap = cv2.VideoCapture(args.camera)
    try:
        if not cap.isOpened():
            logger.error("Could not open webcam at index %d.", args.camera)
            return 2
        if voice is not None:
            voice.speak("Please switch to the camera window and calibrate the board.")
        if not detector.calibrate(cap):
            logger.error("Calibration failed or cancelled.")
            return 1
        if voice is not None:
            voice.speak("Calibration complete. Let's play.")

        validator = BoardStateValidator()
        recommended_board: bytes | None = None
        recommendation: int | None = None
        last_rejection: str | None = None
        rng = np.random.default_rng()
        logger.info("Controls: r = reset board tracking, q = quit.")
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            grid, board_img = detector.process_frame(frame)
            if grid is not None:
                if board_img is not None:
                    cv2.imshow("Board View", board_img)
                check = validator.accept(grid)
                if not check.ok:
                    if check.reason != last_rejection:
                        logger.warning("Board rejected: %s. Press r to resync.", check.reason)
                    last_rejection = check.reason
                else:
                    last_rejection = None
                    valid = available_columns(grid)
                    ai_turn = player_to_move(grid) == _AI_YELLOW
                    if check_winner(grid) or not valid or not ai_turn:
                        recommended_board = None
                        recommendation = None
                    else:
                        board_key = grid.tobytes()
                        if board_key != recommended_board:
                            col = None
                            if model is not None:
                                try:
                                    action, _ = model.predict(
                                        swap_perspective(grid), deterministic=True
                                    )
                                    col = int(action)
                                except Exception as exc:
                                    logger.warning(
                                        "Prediction failed; using legal fallback: %s", exc
                                    )
                            if col not in valid:
                                col = int(rng.choice(valid))
                            recommendation = col
                            recommended_board = board_key
                            if voice is not None:
                                voice.play_move_commentary(col)
                            logger.info("AI suggests column %d", col + 1)
                        if recommendation is not None:
                            detector.draw_move(frame, recommendation)

            cv2.imshow("Main", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                validator.reset()
                recommended_board = None
                recommendation = None
                last_rejection = None
                logger.info("Board tracking reset.")
    finally:
        cap.release()
        try:
            cv2.destroyAllWindows()
        finally:
            if voice is not None:
                voice.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
