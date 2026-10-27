"""Physical-board assistant: read a real board through the webcam.

Two capture modes share one analysis path:

* default (on demand): press SPACE to capture the current board state, run
  the chosen AI opponent, and overlay the recommended column;
* ``--watch``: the board is read every frame, and a reading is analyzed
  only once it has been identical for ``--stable-frames`` consecutive frames
  (hands and falling tokens never reach the AI). New recommendations are
  announced once, by voice when ``--voice`` is on.

Calibration locates the board automatically (press ENTER to accept the
outline, or click the 4 corners), and every validated reading re-fits the
color thresholds to the current lighting. Press 'r' to reset board tracking
and 'q' to quit.

Difficulty tiers (same as ``play_gui.py``):
  easy        Random opponent.
  medium      1-ply heuristic (win/block/center).
  hard        Bitboard alpha-beta search, depth 8. Default.
  impossible  Perfect play: exact opening book, then the exact solver (~3s);
              tactically-safe fallback only for unprovable off-book positions.
  neural      CNN distilled from exact solver labels; no search.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

from pefforza.agent.difficulty import (
    DEFAULT_DIFFICULTY,
    DIFFICULTY_NAMES,
    build_opponent,
    describe_difficulties,
)
from pefforza.agent.evaluate import Agent
from pefforza.constants import DEFAULT_MODEL_PATH
from pefforza.rules import (
    Board,
    available_columns,
    check_winner,
    player_to_move,
    swap_perspective,
)
from pefforza.vision.board_detector import BoardDetector
from pefforza.vision.validation import BoardStateValidator

logger = logging.getLogger(__name__)

Grid = Board
AnalysisKind = Literal["rejected", "resynced", "game_over", "wait", "full", "move"]

DEFAULT_STABLE_FRAMES = 8


@dataclass(frozen=True)
class Analysis:
    """Outcome of analyzing one board reading.

    ``display_col`` is set only for ``kind == "move"`` and is expressed in
    the coordinate system of the grid that was analyzed (the mirrored display
    frame); translate it with :meth:`BoardDetector.physical_col` before
    telling a human which physical column to play.
    """

    kind: AnalysisKind
    message: str
    display_col: int | None = None
    winner: int = 0


class PhysicalAssistant:
    """Turn validated board readings (vision view: 1 = red, 2 = yellow) into advice.

    Pure logic - no camera, window, or audio - so the whole decision path is
    unit-testable with synthetic grids.
    """

    def __init__(
        self,
        agent: Agent,
        *,
        ai_is_red: bool,
        validator: BoardStateValidator | None = None,
    ) -> None:
        self.agent = agent
        self.ai_is_red = ai_is_red
        self.validator = validator if validator is not None else BoardStateValidator()

    @property
    def ai_token(self) -> int:
        return 1 if self.ai_is_red else 2

    def reset(self) -> None:
        self.validator.reset()

    def analyze(self, grid: Grid) -> Analysis:
        check = self.validator.accept(grid)
        if not check.ok:
            # A misread (hand occlusion, mid-drop token, glare) must never
            # reach the AI as a real position.
            return Analysis("rejected", f"Board rejected: {check.reason}.")
        if check.reason is not None:
            # Informational accept, e.g. a new game after the board was cleared.
            return Analysis("resynced", f"Board accepted: {check.reason}.")

        winner = check_winner(grid)
        if winner != 0:
            name = "RED" if winner == 1 else "YELLOW"
            return Analysis("game_over", f"{name} WINS!", winner=winner)

        # The validator already proved the counts are turn-compatible.
        if player_to_move(grid) != self.ai_token:
            return Analysis("wait", "Opponent's turn - waiting for their move.")

        # Agents always see themselves as player 1.
        agent_view = grid.copy() if self.ai_is_red else swap_perspective(grid)
        valid = available_columns(agent_view)
        if not valid:
            return Analysis("full", "Board is full.")
        col = int(self.agent(agent_view, 1, valid))
        if col not in valid:
            col = valid[0]
        return Analysis("move", "AI move ready.", display_col=col)


class StableGridFilter:
    """Debounce a stream of per-frame grid readings for ``--watch`` mode.

    :meth:`update` returns a grid only when the same reading has been seen
    for ``frames`` consecutive frames *and* differs from the last grid it
    returned, so each settled board state is analyzed exactly once.
    """

    def __init__(self, frames: int = DEFAULT_STABLE_FRAMES) -> None:
        if frames < 1:
            raise ValueError("frames must be >= 1")
        self.frames = frames
        self._candidate: Grid | None = None
        self._streak = 0
        self._emitted: Grid | None = None

    def reset(self) -> None:
        self._candidate = None
        self._streak = 0
        self._emitted = None

    def update(self, grid: Grid | None) -> Grid | None:
        if grid is None:
            self._candidate = None
            self._streak = 0
            return None
        if self._candidate is not None and np.array_equal(grid, self._candidate):
            self._streak += 1
        else:
            self._candidate = grid.copy()
            self._streak = 1
        if self._streak < self.frames:
            return None
        if self._emitted is not None and np.array_equal(self._candidate, self._emitted):
            return None
        self._emitted = self._candidate.copy()
        return self._emitted.copy()


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
    p.add_argument(
        "--watch",
        action="store_true",
        help="Analyze continuously instead of on SPACE (debounced, see --stable-frames).",
    )
    p.add_argument(
        "--stable-frames",
        type=int,
        default=DEFAULT_STABLE_FRAMES,
        help=(
            "--watch only: identical consecutive readings required before a board "
            f"is analyzed (default: {DEFAULT_STABLE_FRAMES})."
        ),
    )
    p.add_argument(
        "--voice",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Announce recommendations with text-to-speech.",
    )
    p.add_argument("--seed", type=int, default=None)
    args = p.parse_args(argv)
    if args.stable_frames < 1:
        p.error("--stable-frames must be >= 1")
    return args


def _prompt_ai_color() -> bool:
    print("\nWho should the AI play as?")
    print("  1. Red    (plays first)")
    print("  2. Yellow (plays second)")
    while True:
        choice = input("Enter 1 or 2: ").strip()
        if choice in {"1", "2"}:
            return choice == "1"
        print("Invalid choice.")


def _make_voice(enabled: bool):  # -> VoiceEngine | None
    if not enabled:
        return None
    try:
        from pefforza.interaction.voice import VoiceEngine

        return VoiceEngine()
    except Exception as exc:  # voice is optional and must never stop the game
        logger.warning("Voice disabled: %s", exc)
        return None


def _put_text(frame, text: str, y: int, scale: float, color: tuple[int, int, int], width: int):
    cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, width)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args(argv)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        logger.error("Could not open webcam at index %d.", args.camera)
        return 2

    voice = _make_voice(args.voice)
    try:
        ai_is_red = (args.ai_color == "red") if args.ai_color else _prompt_ai_color()
        ai_color_name = "RED" if ai_is_red else "YELLOW"
        print(f"AI will play as {ai_color_name} at difficulty: {args.difficulty}")

        assistant = PhysicalAssistant(
            build_opponent(args.difficulty, seed=args.seed, model_path=args.model),
            ai_is_red=ai_is_red,
        )
        stable = StableGridFilter(args.stable_frames)
        detector = BoardDetector()

        if voice is not None:
            voice.speak("Please switch to the camera window and calibrate the board.")
        print("\nStarting calibration: the board is located automatically - press ENTER")
        print("once it is outlined, or click its 4 corners (any order). 'q' aborts.")
        if not detector.calibrate(cap, flip=True):
            logger.error("Calibration failed or cancelled.")
            return 1
        if voice is not None:
            voice.speak("Calibration complete. Let's play.")

        trigger = "watching" if args.watch else "SPACE to analyze"
        print(f"Controls: {'' if args.watch else '[SPACE] analyze | '}[r] reset | [q] quit")
        last_recommendation: int | None = None
        game_over_message: str | None = None

        def analyze(grid: Grid, warped) -> None:
            result = assistant.analyze(grid)
            # A validated reading is ground truth for the current lighting:
            # re-fit the color thresholds to it (committed only if the new
            # profile reproduces this exact reading).
            if (
                result.kind != "rejected"
                and warped is not None
                and detector.adapt_colors(warped, grid)
            ):
                logger.debug("Color thresholds adapted to the current lighting.")
            report(result)

        def report(result: Analysis) -> None:
            nonlocal last_recommendation, game_over_message
            if result.kind == "rejected":
                print(result.message)
                if not args.watch:
                    print("Let the board settle and press SPACE again, or press 'r' to resync.")
                return
            last_recommendation = None
            game_over_message = None
            if result.kind == "game_over":
                game_over_message = result.message
                print(f"Game over: {result.message}")
                if voice is not None:
                    voice.speak(result.message.capitalize())
            elif result.kind == "move" and result.display_col is not None:
                # The arrow is drawn in display space (the mirrored frame the
                # grid was classified in); the human counts columns on the
                # physical board, whose left-right order is the opposite.
                last_recommendation = result.display_col
                physical_col = detector.physical_col(result.display_col)
                print(
                    f"AI ({ai_color_name}, {args.difficulty}) "
                    f"recommends physical column {physical_col + 1}"
                )
                if voice is not None:
                    voice.play_move_commentary(physical_col)
            else:
                print(result.message)

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
                assistant.reset()
                stable.reset()
                last_recommendation = None
                game_over_message = None
                print("Board tracking reset: the next analyzed state starts a new history.")

            if args.watch:
                grid, warped = detector.process_frame(frame)
                settled = stable.update(grid)
                if settled is not None:
                    analyze(settled, warped)
            elif key == ord(" "):
                grid, warped = detector.process_frame(frame)
                if grid is None:
                    print("Could not process board; check calibration.")
                else:
                    print("\nDetected board:")
                    print(grid)
                    analyze(grid, warped)

            _put_text(
                display,
                f"AI: {ai_color_name} ({args.difficulty}) | {trigger}",
                30,
                0.7,
                (0, 255, 0),
                2,
            )
            if detector.matrix is not None:
                detector.draw_overlays(display)
            if last_recommendation is not None:
                detector.draw_move(display, last_recommendation)
                recommended = detector.physical_col(last_recommendation) + 1
                _put_text(
                    display, f"AI Recommends: physical column {recommended}", 60, 1, (0, 0, 255), 2
                )
            if game_over_message:
                _put_text(display, game_over_message, 100, 1.5, (255, 0, 255), 3)

            cv2.imshow("Connect 4 - AI Assistant", display)
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if voice is not None:
            voice.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
