"""Physical-board assistant: analyze the live webcam feed on demand.

Press SPACE to capture the current board state, run the chosen AI
opponent, and overlay the recommended column. Press 'q' to quit.

Difficulty tiers (same as ``play_gui.py``):
  easy        Random opponent.
  medium      1-ply heuristic (win/block/center).
  hard        Bitboard alpha-beta search, depth 8. Default.
  impossible  Exact solver, ~3s budget: proven-optimal once provable, else a
              tactically-safe fallback (never gifts an immediate win).
  neural      Wraps the bundled PPO checkpoint.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import cv2

from pefforza.agent.difficulty import (
    DEFAULT_DIFFICULTY,
    DIFFICULTY_NAMES,
    describe_difficulties,
)
from pefforza.cli.gui_game import OpponentWorker
from pefforza.constants import DEFAULT_MODEL_PATH
from pefforza.rules import (
    available_columns,
    check_winner,
    is_board_full,
    player_to_move,
    swap_perspective,
)
from pefforza.vision.board_detector import BoardDetector
from pefforza.vision.validation import BoardStateValidator

logger = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Physical Connect 4 assistant.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Difficulty tiers:\n" + describe_difficulties(),
    )
    p.add_argument(
        "--difficulty",
        choices=DIFFICULTY_NAMES,
        default=DEFAULT_DIFFICULTY,
        help=f"AI strength (default: {DEFAULT_DIFFICULTY}).",
    )
    p.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help=f"Checkpoint used by --difficulty=neural (default: {DEFAULT_MODEL_PATH}).",
    )
    p.add_argument("--camera", type=int, default=0)
    p.add_argument(
        "--ai-color",
        choices=["red", "yellow"],
        default=None,
        help="Skip the interactive prompt by setting the AI color upfront.",
    )
    p.add_argument("--seed", type=int, default=None)
    return p.parse_args(argv)


def _prompt_ai_color() -> bool:
    print("\nWho should the AI play as?")
    print("  1. Red    (plays first)")
    print("  2. Yellow (plays second)")
    while True:
        choice = input("Enter 1 or 2: ").strip()
        if choice in {"1", "2"}:
            return choice == "1"
        print("Invalid choice.")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args(argv)

    cap = cv2.VideoCapture(args.camera)
    worker = OpponentWorker(args.difficulty, seed=args.seed, model_path=args.model)
    try:
        if not cap.isOpened():
            logger.error("Could not open webcam at index %d.", args.camera)
            return 2
        ai_is_red = (args.ai_color == "red") if args.ai_color else _prompt_ai_color()
        ai_color_name = "RED" if ai_is_red else "YELLOW"
        print(f"AI will play as {ai_color_name} at difficulty: {args.difficulty}")

        detector = BoardDetector()
        validator = BoardStateValidator()
        print("\nStarting calibration: click the 4 corners of the board. Press 'q' to abort.")
        print("Order doesn't matter - we auto-detect TL/TR/BR/BL.")
        if not detector.calibrate(cap, flip=True):
            logger.error("Calibration failed or cancelled.")
            return 1

        print("Controls: [SPACE] analyze | [r] reset board tracking | [q] quit")
        last_recommendation: int | None = None
        game_over_message: str | None = None

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            display = frame.copy()

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                worker.cancel()
                validator.reset()
                last_recommendation = None
                game_over_message = None
                print("Board tracking reset: the next analyzed state starts a new history.")
            if key == ord(" "):
                worker.cancel()
                last_recommendation = None
                game_over_message = None
                grid, _ = detector.process_frame(frame)
                check = validator.accept(grid) if grid is not None else None
                if grid is None or check is None:
                    print("Could not process board; check calibration.")
                elif not check.ok:
                    # A misread (hand occlusion, mid-drop token, glare) must
                    # never reach the AI as a real position.
                    print(f"Board rejected: {check.reason}.")
                    print("Let the board settle and press SPACE again, or press 'r' to resync.")
                elif check.reason is not None:
                    # Informational accept, e.g. new game detected after the
                    # board was cleared. Press SPACE again to get a move.
                    print(f"Board accepted: {check.reason}.")
                    last_recommendation = None
                    game_over_message = None
                else:
                    print("\nDetected board:")
                    print(grid)
                    winner = check_winner(grid)
                    if winner != 0:
                        game_over_message = "RED WINS!" if winner == 1 else "YELLOW WINS!"
                        last_recommendation = None
                        print(f"Game over: {game_over_message}")
                    elif is_board_full(grid):
                        game_over_message = "DRAW!"
                        print("Game over: DRAW! Board is full.")
                    else:
                        game_over_message = None
                        # Only consult the AI on its own turn. Vision view is
                        # 1 = red / 2 = yellow; the validator already proved
                        # the counts are turn-compatible.
                        turn = player_to_move(grid)
                        ai_token = 1 if ai_is_red else 2
                        if turn != ai_token:
                            print(
                                "Board accepted. Opponent's turn - "
                                "press SPACE after their move lands."
                            )
                            last_recommendation = None
                        else:
                            # Translate vision view (1=Red, 2=Yellow) into agent
                            # view (1 = "self"). If AI plays Yellow, swap.
                            agent_view = grid.copy() if ai_is_red else swap_perspective(grid)
                            valid = available_columns(agent_view)
                            if not valid:
                                print("Board is full.")
                            else:
                                worker.request(agent_view, 1)

            # Poll only after handling resync/new analyses: an old result must
            # never escape cancellation and be drawn over a newly read board.
            col = worker.poll()
            if col is not None:
                last_recommendation = col
                physical_col = detector.physical_col(col)
                print(
                    f"AI ({ai_color_name}, {worker.active_difficulty}) "
                    f"recommends physical column {physical_col + 1}"
                )
                if worker.error:
                    logger.warning(worker.error)

            cv2.putText(
                display,
                f"AI: {ai_color_name} ({worker.active_difficulty}) | SPACE to analyze",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )
            if detector.matrix is not None:
                detector.draw_overlays(display)
            if worker.busy:
                cv2.putText(
                    display,
                    "Thinking... | r to cancel | q to quit",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2,
                )
            if last_recommendation is not None:
                detector.draw_move(display, last_recommendation)
                recommended = detector.physical_col(last_recommendation) + 1
                cv2.putText(
                    display,
                    f"AI Recommends: physical column {recommended}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    2,
                )
            if game_over_message:
                cv2.putText(
                    display,
                    game_over_message,
                    (10, 100),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.5,
                    (255, 0, 255),
                    3,
                )

            cv2.imshow("Connect 4 - AI Assistant", display)
    finally:
        try:
            worker.close()
        finally:
            cap.release()
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
