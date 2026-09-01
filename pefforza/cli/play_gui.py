"""Pygame GUI for Connect 4 against a selectable-difficulty AI."""

from __future__ import annotations

import argparse
import contextlib
import logging
import math
import sys
from pathlib import Path

import numpy as np
import pygame

from pefforza.agent.difficulty import (
    DEFAULT_DIFFICULTY,
    DIFFICULTY_NAMES,
    build_opponent,
    describe_difficulties,
)
from pefforza.agent.minimax import find_immediate_win
from pefforza.constants import COLS, DEFAULT_MODEL_PATH, ROWS
from pefforza.envs.connect4_env import Connect4Env
from pefforza.rules import available_columns, next_open_row

logger = logging.getLogger(__name__)

# Visual constants
BLUE = (0, 0, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
WHITE = (240, 240, 240)

SQUARESIZE = 100
RADIUS = SQUARESIZE // 2 - 5
WIDTH = COLS * SQUARESIZE
HEIGHT = (ROWS + 1) * SQUARESIZE


def draw_board(screen: pygame.Surface, board: np.ndarray) -> None:
    for c in range(COLS):
        for r in range(ROWS):
            pygame.draw.rect(
                screen,
                BLUE,
                (c * SQUARESIZE, (r + 1) * SQUARESIZE, SQUARESIZE, SQUARESIZE),
            )
            pygame.draw.circle(
                screen,
                BLACK,
                (c * SQUARESIZE + SQUARESIZE // 2, (r + 1) * SQUARESIZE + SQUARESIZE // 2),
                RADIUS,
            )
    for c in range(COLS):
        for r in range(ROWS):
            v = board[r, c]
            if v == 1:
                color = RED
            elif v == 2:
                color = YELLOW
            else:
                continue
            pygame.draw.circle(
                screen,
                color,
                (c * SQUARESIZE + SQUARESIZE // 2, (r + 1) * SQUARESIZE + SQUARESIZE // 2),
                RADIUS,
            )
    pygame.display.update()


def draw_status(screen: pygame.Surface, font: pygame.font.Font, text: str) -> None:
    pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, SQUARESIZE))
    label = font.render(text, True, WHITE)
    screen.blit(label, (10, SQUARESIZE - 30))
    pygame.display.update()


# Animation tuning. Kept short so the game flow doesn't drag.
_ANIM_DURATION_PER_ROW_MS = 50  # roughly time-per-row drop
_ANIM_MIN_DURATION_MS = 180  # always at least this long, even for 1-row drops
_ANIM_FPS = 120


def _column_center_x(col: int) -> int:
    return col * SQUARESIZE + SQUARESIZE // 2


def _row_center_y(row: int) -> int:
    """Pixel y for the center of a circle at logical row ``row`` (0..ROWS-1)."""
    return (row + 1) * SQUARESIZE + SQUARESIZE // 2


def _render_board_surface(board: np.ndarray) -> pygame.Surface:
    """Pre-render a static board snapshot so animation frames blit instead of redraw."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill(BLACK)
    # Top "preview" row stays black; we only paint the playing area.
    for c in range(COLS):
        for r in range(ROWS):
            pygame.draw.rect(
                surf,
                BLUE,
                (c * SQUARESIZE, (r + 1) * SQUARESIZE, SQUARESIZE, SQUARESIZE),
            )
            v = board[r, c]
            if v == 1:
                color = RED
            elif v == 2:
                color = YELLOW
            else:
                color = BLACK
            pygame.draw.circle(
                surf,
                color,
                (c * SQUARESIZE + SQUARESIZE // 2, (r + 1) * SQUARESIZE + SQUARESIZE // 2),
                RADIUS,
            )
    return surf


def animate_drop(
    screen: pygame.Surface,
    board_before: np.ndarray,
    col: int,
    target_row: int,
    player: int,
) -> None:
    """Animate a piece falling into ``(target_row, col)``.

    Strategy:
    * Pre-render the static board to a Surface once. Each frame blits that
      surface and overlays one falling circle. ~10x cheaper than rebuilding
      the whole grid each frame, which kills flicker.
    * Quadratic ease-in (t**2) approximates gravity.
    * 120 Hz target with a *local* ``Clock`` for frame pacing, but elapsed
      animation time is measured via ``pygame.time.get_ticks()``. This is
      important: a Clock shared with a calling loop that just blocked for
      seconds (e.g. a 3s minimax search) would have its first ``tick`` call
      return that whole pause as elapsed, instantly skipping the animation.
    """
    color = RED if player == 1 else YELLOW
    board_surface = _render_board_surface(board_before)

    start_y = SQUARESIZE // 2  # middle of the preview row
    end_y = _row_center_y(target_row)
    cx = _column_center_x(col)

    duration_ms = max(
        _ANIM_MIN_DURATION_MS,
        _ANIM_DURATION_PER_ROW_MS * (target_row + 1),
    )

    clock = pygame.time.Clock()  # fresh clock - frame pacing only
    start_ticks = pygame.time.get_ticks()
    quit_requested = False

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.event.post(event)
                quit_requested = True
                break
        if quit_requested:
            break

        elapsed = pygame.time.get_ticks() - start_ticks
        if elapsed >= duration_ms:
            break

        # Quadratic ease-in: t**2 gives a "falling under gravity" feel.
        t = elapsed / duration_ms
        y = start_y + (end_y - start_y) * (t * t)

        screen.blit(board_surface, (0, 0))
        pygame.draw.circle(screen, color, (cx, int(y)), RADIUS)
        pygame.display.update()
        clock.tick_busy_loop(_ANIM_FPS)

    # Final frame: piece exactly at the landing position.
    screen.blit(board_surface, (0, 0))
    pygame.draw.circle(screen, color, (cx, end_y), RADIUS)
    pygame.display.update()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Play Connect 4 with a Pygame GUI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Difficulty tiers:\n" + describe_difficulties(),
    )
    p.add_argument(
        "--difficulty",
        choices=DIFFICULTY_NAMES,
        default=DEFAULT_DIFFICULTY,
        help=f"Opponent strength (default: {DEFAULT_DIFFICULTY}).",
    )
    p.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument(
        "--no-animate",
        action="store_true",
        help="Skip the falling-piece animation (instant placement).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    # Configure logging once. Watchdog warnings go to stderr AND to a log file
    # so we can review them even after the GUI window closes.
    log_file = Path("watchdog.log")
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    with contextlib.suppress(OSError):
        handlers.append(logging.FileHandler(log_file, mode="w", encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )
    logger.info("Watchdog log: %s", log_file.resolve())

    pygame.init()
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(f"Connect 4 - difficulty: {args.difficulty}")
        font = pygame.font.SysFont("monospace", 60)
        small = pygame.font.SysFont("monospace", 22)

        env = Connect4Env()
        obs, _ = env.reset(seed=args.seed)
        opponent = build_opponent(args.difficulty, seed=args.seed, model_path=args.model)
        logger.info("Difficulty: %s", args.difficulty)

        draw_board(screen, obs)
        draw_status(screen, small, f"Difficulty: {args.difficulty}  -  Your turn")

        game_over = False
        message = ""
        watchdog_triggered = False

        clock = pygame.time.Clock()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 0

                if not game_over and event.type == pygame.MOUSEMOTION:
                    pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, SQUARESIZE))
                    pygame.draw.circle(screen, RED, (event.pos[0], SQUARESIZE // 2), RADIUS)
                    pygame.display.update()

                if (
                    not game_over
                    and event.type == pygame.MOUSEBUTTONDOWN
                    and env.current_player == 1
                ):
                    pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, SQUARESIZE))
                    col = int(math.floor(event.pos[0] / SQUARESIZE))
                    if 0 <= col < COLS and obs[0, col] == 0:
                        if not args.no_animate:
                            target_row = next_open_row(env.board, col)
                            animate_drop(
                                screen,
                                env.board.copy(),
                                col,
                                target_row,
                                player=1,
                            )
                        obs, reward, terminated, _, _ = env.step(col)
                        draw_board(screen, obs)
                        if terminated:
                            message = "You win!" if reward == 1 else "Draw"
                            game_over = True

            if not game_over and env.current_player == 2:
                # Show "thinking" so the GUI doesn't feel frozen during deeper search.
                draw_status(screen, small, f"Difficulty: {args.difficulty}  -  AI thinking...")
                pygame.event.pump()
                valid = available_columns(env.board)
                if valid:
                    # Watchdog: snapshot threats before the AI moves so we can
                    # detect (and report) any failure to block an obvious win.
                    pre_board = env.board.copy()
                    human_immediate_win = find_immediate_win(pre_board, 1, valid)
                    ai_immediate_win = find_immediate_win(pre_board, 2, valid)

                    col = opponent(env.board, env.current_player, valid)
                    if col not in valid:
                        col = valid[0]
                    if not args.no_animate:
                        # Clear the "AI thinking..." status before the drop so
                        # the falling piece is visible from the very first
                        # frame (the status sits in the same row).
                        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, SQUARESIZE))
                        pygame.display.update()
                        target_row = next_open_row(env.board, col)
                        animate_drop(
                            screen,
                            env.board.copy(),
                            col,
                            target_row,
                            player=2,
                        )
                    obs, reward, terminated, _, _ = env.step(col)

                    # If the human had an immediate win, the AI is required to
                    # either block it or take its own immediate win. If neither,
                    # log a clear, copy-pasteable diagnostic.
                    if (
                        human_immediate_win is not None
                        and col != human_immediate_win
                        and (ai_immediate_win is None or col != ai_immediate_win)
                    ):
                        diag = "\n".join(
                            "  "
                            + " ".join(
                                "X" if v == 1 else "O" if v == 2 else "." for v in pre_board[r]
                            )
                            for r in range(ROWS)
                        )
                        logger.error(
                            "WATCHDOG: AI ignored a blockable threat.\n"
                            "  Difficulty: %s\n"
                            "  Human could win at column %d, AI played %d.\n"
                            "  AI's own immediate win was at: %s\n"
                            "Board before AI move:\n%s\n  %s",
                            args.difficulty,
                            human_immediate_win,
                            col,
                            ai_immediate_win,
                            diag,
                            " ".join(str(c) for c in range(COLS)),
                        )
                        watchdog_triggered = True

                    draw_board(screen, obs)
                    if terminated:
                        message = "AI wins" if reward == 1 else "Draw"
                        game_over = True
                    else:
                        draw_status(screen, small, f"Difficulty: {args.difficulty}  -  Your turn")

            if game_over and message:
                pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, SQUARESIZE))
                color = RED if "win" in message and "AI" not in message else YELLOW
                label = font.render(message, True, color)
                screen.blit(label, (40, 10))
                if watchdog_triggered:
                    warn = small.render(
                        "WATCHDOG fired - see watchdog.log",
                        True,
                        (255, 80, 80),
                    )
                    screen.blit(warn, (10, SQUARESIZE - 22))
                pygame.display.update()
                pygame.time.wait(5000 if watchdog_triggered else 3000)
                return 0

            clock.tick(60)
    finally:
        pygame.quit()


if __name__ == "__main__":
    sys.exit(main())
