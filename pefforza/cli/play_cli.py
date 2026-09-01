"""Terminal Connect 4 against an AI opponent.

The opponent is selectable via ``--difficulty`` (easy / medium / hard /
impossible / neural). See :mod:`pefforza.agent.difficulty` for what each
tier means.

Pre-validates the human's column choice so a typo never ends the game,
and falls back to a random valid action if an agent ever returns an
illegal column.
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from pathlib import Path

import numpy as np

from pefforza.agent.difficulty import (
    DEFAULT_DIFFICULTY,
    DIFFICULTY_NAMES,
    build_opponent,
    describe_difficulties,
)
from pefforza.constants import COLS, DEFAULT_MODEL_PATH
from pefforza.envs.connect4_env import Connect4Env
from pefforza.rules import available_columns

logger = logging.getLogger(__name__)

try:
    from pefforza.interaction.voice import VoiceEngine

    _VOICE_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency at runtime
    VoiceEngine = None  # type: ignore[assignment,misc]
    _VOICE_AVAILABLE = False


def print_board(board: np.ndarray) -> None:
    print("\n  1 2 3 4 5 6 7")
    print("  -------------")
    for r in range(board.shape[0]):
        cells = []
        for v in board[r]:
            cells.append("X" if v == 1 else "O" if v == 2 else " ")
        print("| " + " ".join(cells) + " |")
    print("  -------------\n")


def get_human_action(valid: list[int]) -> int:
    while True:
        raw = input("Your turn (X). Choose column (1-7): ").strip()
        try:
            col = int(raw) - 1
        except ValueError:
            print("Invalid input. Please enter a number.")
            continue
        if col in valid:
            return col
        if 0 <= col < COLS:
            print("That column is full. Pick another.")
        else:
            print(f"Please enter a number between 1 and {COLS}.")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Play Connect 4 in the terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Difficulty tiers:\n" + describe_difficulties(),
    )
    p.add_argument(
        "--difficulty",
        choices=DIFFICULTY_NAMES,
        default=DEFAULT_DIFFICULTY,
        help=f"Opponent strength (default: {DEFAULT_DIFFICULTY}).",
    )
    p.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help=f"Checkpoint used by --difficulty=neural (default: {DEFAULT_MODEL_PATH}).",
    )
    p.add_argument("--voice", action="store_true", help="Enable text-to-speech commentary.")
    p.add_argument("--seed", type=int, default=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args(argv)

    if args.seed is not None:
        random.seed(args.seed)

    env = Connect4Env(render_mode=None)
    opponent = build_opponent(args.difficulty, seed=args.seed, model_path=args.model)
    print(f"Playing against difficulty: {args.difficulty}")

    voice = None
    if args.voice and _VOICE_AVAILABLE:
        try:
            voice = VoiceEngine()
            voice.speak("Welcome to Digital Connect 4. You are Player X.")
        except Exception as exc:
            logger.warning("Voice init failed: %s", exc)

    obs, _ = env.reset(seed=args.seed)
    terminated = False
    truncated = False
    last_mover: str | None = None
    last_reward = 0.0
    info: dict = {}

    print("Game Start. You are 'X' (Player 1). AI is 'O' (Player 2).")
    print_board(obs)

    try:
        while not (terminated or truncated):
            valid = available_columns(env.board)
            if not valid:
                break

            if env.current_player == 1:
                action = get_human_action(valid)
                last_mover = "Human"
                obs, last_reward, terminated, truncated, info = env.step(action)
            else:
                print("AI is thinking...")
                t0 = time.perf_counter()
                action = opponent(env.board, env.current_player, valid)
                if action not in valid:
                    action = valid[0]
                think_time = time.perf_counter() - t0
                last_mover = "AI"
                print(f"AI chose column {action + 1}  ({think_time:.2f}s)")
                if voice is not None:
                    voice.play_move_commentary(action, confidence=0.8)
                obs, last_reward, terminated, truncated, info = env.step(action)
            print_board(obs)

        # Report the result while the voice worker is still alive: the finally
        # clause below shuts it down, and phrases queued after that would
        # never be spoken.
        if "error" in info:
            print(f"Game ended due to invalid move: {info['error']}")
        elif last_reward == 1.0 and last_mover is not None:
            print(f"\n{last_mover} wins.\n")
            if voice is not None:
                voice.speak(
                    "Congratulations, you have defeated me."
                    if last_mover == "Human"
                    else "I have won. Better luck next time."
                )
        elif terminated:
            print("\nIt's a draw.\n")
            if voice is not None:
                voice.speak("It is a draw.")
    except (KeyboardInterrupt, EOFError):
        print("\nGame interrupted.")
        return 130
    finally:
        if voice is not None:
            voice.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
