"""A responsive desktop playground for Connect Four."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pygame

from pefforza.agent.difficulty import (
    DEFAULT_DIFFICULTY,
    DIFFICULTY_NAMES,
    describe_difficulties,
)
from pefforza.cli.gui_game import GameSession, OpponentWorker
from pefforza.cli.gui_view import (
    BG,
    BUTTONS,
    HEIGHT,
    WIDTH,
    GameView,
    column_at,
    map_pointer,
    viewport,
)
from pefforza.cli.lessons import LESSONS
from pefforza.constants import COLS, DEFAULT_MODEL_PATH
from pefforza.rules import next_open_row

logger = logging.getLogger(__name__)


class GameApp:
    """Event-driven desktop state; search never runs on the drawing thread."""

    def __init__(
        self,
        difficulty: str = DEFAULT_DIFFICULTY,
        seed: int | None = None,
        model_path: Path = DEFAULT_MODEL_PATH,
        animate: bool = True,
    ) -> None:
        self.difficulty = difficulty
        self.seed = seed
        self.model_path = model_path
        self.animate = animate
        self.session = GameSession(seed=seed)
        self.worker = OpponentWorker(difficulty, seed=seed, model_path=model_path)
        self.selected_col = COLS // 2
        self.hint_col: int | None = None
        self.animation: tuple[int, int, int, int] | None = None
        self.animation_duration = 0
        self.notice = ""
        self.running = True
        self.lesson_index: int | None = None
        self.lesson_attempted = False
        self.lesson_solved = False

    def load_lesson(self, index: int) -> None:
        self.lesson_index = index % len(LESSONS)
        self.restart()

    @property
    def opponent_label(self) -> str:
        active = self.worker.active_difficulty
        if active == "fallback":
            return "Legal fallback"
        if active != self.difficulty:
            return f"{active.title()} (fallback)"
        return self.difficulty.title()

    def restart(self) -> None:
        self.worker.cancel()
        self.animation = None
        self.hint_col = None
        self.notice = ""
        self.session.restart()
        self.lesson_attempted = False
        self.lesson_solved = False
        if self.lesson_index is not None:
            lesson = LESSONS[self.lesson_index]
            for col in lesson.moves:
                self.session.play(col)
            self.session.status = lesson.prompt

    def commit_drop(self, col: int) -> None:
        if not self.session.play(col):
            return
        if self.lesson_index is not None:
            lesson = LESSONS[self.lesson_index]
            self.lesson_attempted = True
            self.lesson_solved = col in lesson.answers
            if self.lesson_solved:
                self.session.status = lesson.explanation
            else:
                self.session.status = "Not quite. Press U to retry, or H for an explanation."

    def command(self, name: str) -> None:
        if name == "lessons":
            if self.lesson_index is None:
                self.load_lesson(0)
            else:
                self.lesson_index = None
                self.restart()
            return
        if self.lesson_index is not None:
            if name in ("next", "difficulty"):
                self.load_lesson(self.lesson_index + 1)
            elif name in ("restart", "undo"):
                self.restart()
            elif name == "hint" and self.animation is None:
                lesson = LESSONS[self.lesson_index]
                self.session.status = lesson.explanation
                if not self.lesson_attempted:
                    self.hint_col = self.selected_col = lesson.answers[0]
            return
        if name == "restart":
            self.restart()
        elif name == "undo":
            pending_human = self.animation is not None and self.animation[2] == 1
            self.worker.cancel()
            self.animation = None
            self.hint_col = None
            self.notice = ""
            if pending_human:
                self.session.status = "Drop cancelled. Your turn."
            else:
                self.session.undo()
        elif name == "hint" and self.animation is None:
            self.notice = ""
            self.hint_col = self.session.hint()
            if self.hint_col is not None:
                self.selected_col = self.hint_col
        elif name == "difficulty":
            index = (DIFFICULTY_NAMES.index(self.difficulty) + 1) % len(DIFFICULTY_NAMES)
            self.worker.close()
            self.difficulty = DIFFICULTY_NAMES[index]
            self.worker = OpponentWorker(
                self.difficulty, seed=self.seed, model_path=self.model_path
            )
            self.restart()

    def drop(self, col: int, now: int) -> None:
        if self.lesson_index is not None and self.lesson_attempted:
            return
        if self.session.game_over or self.animation is not None or not 0 <= col < COLS:
            return
        row = next_open_row(self.session.board, col)
        if row < 0:
            self.notice = "That column is full. Try another one."
            return
        self.notice = ""
        self.hint_col = None
        if self.animate:
            self.animation_duration = max(180, (row + 1) * 45)
            self.animation = (col, row, self.session.current_player, now)
        else:
            self.commit_drop(col)

    def handle_event(self, event: pygame.event.Event, now: int) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.MOUSEMOTION:
            col = column_at(event.pos)
            if col is not None:
                self.selected_col = col
                self.hint_col = None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, rect in BUTTONS.items():
                if rect.collidepoint(event.pos):
                    self.command(name)
                    return
            col = column_at(event.pos)
            if col is not None and self.session.current_player == 1:
                self.selected_col = col
                self.drop(col, now)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.key in (
                pygame.K_r,
                pygame.K_u,
                pygame.K_h,
                pygame.K_d,
                pygame.K_l,
                pygame.K_n,
            ):
                self.command(
                    {
                        pygame.K_r: "restart",
                        pygame.K_u: "undo",
                        pygame.K_h: "hint",
                        pygame.K_d: "difficulty",
                        pygame.K_l: "lessons",
                        pygame.K_n: "next",
                    }[event.key]
                )
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.hint_col = None
                self.selected_col = (
                    self.selected_col + (1 if event.key == pygame.K_RIGHT else -1)
                ) % COLS
            elif self.session.current_player == 1:
                if pygame.K_1 <= event.key <= pygame.K_7:
                    self.selected_col = event.key - pygame.K_1
                    self.drop(self.selected_col, now)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.drop(self.selected_col, now)

    def tick(self, now: int) -> None:
        if not self.running:
            return
        if self.animation is not None:
            col, _row, _player, start = self.animation
            if now - start < self.animation_duration:
                return
            self.animation = None
            self.commit_drop(col)
        if self.lesson_index is not None:
            return
        if self.session.game_over or self.session.current_player == 1:
            return
        if not self.worker.busy:
            self.worker.request(self.session.board, self.session.current_player)
        ai_col = self.worker.poll()
        if ai_col is not None:
            self.drop(ai_col, now)
            if self.worker.error:
                logger.warning("AI fallback: %s", self.worker.error)
                self.notice = "AI unavailable this turn; a legal fallback was played."

    def close(self) -> None:
        self.worker.close()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Play Connect Four. Click or use 1-7; R new round, U undo, H hint, D difficulty."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Difficulty tiers:\n" + describe_difficulties(),
    )
    parser.add_argument("--difficulty", choices=DIFFICULTY_NAMES, default=DEFAULT_DIFFICULTY)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--lessons", action="store_true", help="Start with six tactical lessons.")
    parser.add_argument("--no-animate", action="store_true", help="Place pieces without motion.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    pygame.display.init()
    pygame.font.init()
    app = GameApp(args.difficulty, args.seed, args.model, animate=not args.no_animate)
    if args.lessons:
        app.load_lesson(0)
    try:
        desktop = pygame.display.Info()
        size = (min(WIDTH, desktop.current_w - 80), min(HEIGHT, desktop.current_h - 80))
        window = pygame.display.set_mode(size, pygame.RESIZABLE)
        screen = pygame.Surface((WIDTH, HEIGHT))
        pygame.display.set_caption("Pefforza 4 | One more round?")
        view = GameView()
        clock = pygame.time.Clock()
        while app.running:
            now = pygame.time.get_ticks()
            area = viewport(window.get_size())
            for event in pygame.event.get():
                mapped = map_pointer(event, area)
                if mapped is not None:
                    app.handle_event(mapped, now)
            app.tick(now)
            view.draw(screen, app, now)
            window.fill(BG)
            window.blit(pygame.transform.smoothscale(screen, area.size), area)
            pygame.display.flip()
            clock.tick(60)
    finally:
        app.close()
        pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
