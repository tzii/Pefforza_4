"""Live AR Connect 4 assistant (default: AI plays Yellow, human Red).

Watches the webcam, detects the board state, and announces / draws the AI's
recommended move whenever it's the AI's turn.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import cv2
import numpy as np

from pefforza.constants import COLS, DEFAULT_MODEL_PATH
from pefforza.interaction.voice import VoiceEngine
from pefforza.vision.board_detector import BoardDetector

logger = logging.getLogger(__name__)

try:
    from stable_baselines3 import PPO  # type: ignore
except Exception:  # pragma: no cover
    PPO = None  # type: ignore[assignment]

# Vision palette: 1 = Red, 2 = Yellow.
_HUMAN_RED = 1
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
    if not cap.isOpened():
        logger.error("Could not open webcam at index %d.", args.camera)
        return 2

    try:
        if voice is not None:
            voice.speak("Please switch to the camera window and calibrate the board.")
        if not detector.calibrate(cap):
            logger.error("Calibration failed or cancelled.")
            return 1
        if voice is not None:
            voice.speak("Calibration complete. Let's play.")

        ai_announced = False
        rng = np.random.default_rng()
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            grid, board_img = detector.process_frame(frame)
            if grid is not None:
                cv2.imshow("Board View", board_img)
                human_tokens = int(np.count_nonzero(grid == _HUMAN_RED))
                ai_tokens = int(np.count_nonzero(grid == _AI_YELLOW))
                ai_turn = human_tokens > ai_tokens

                if ai_turn:
                    # Translate vision view -> model view (model is "1").
                    model_input = grid.copy()
                    model_input[grid == _AI_YELLOW] = 1
                    model_input[grid == _HUMAN_RED] = 2

                    if model is not None:
                        action, _ = model.predict(model_input, deterministic=True)
                        col = int(action)
                    else:
                        col = int(rng.integers(0, COLS))

                    detector.draw_move(frame, col)
                    if not ai_announced:
                        if voice is not None:
                            voice.play_move_commentary(col, confidence=0.9)
                        logger.info("AI suggests column %d", col + 1)
                        ai_announced = True
                else:
                    ai_announced = False

            cv2.imshow("Main", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if voice is not None:
            voice.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
