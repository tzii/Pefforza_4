"""Pygame drawing and hit targets for the desktop game."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from pefforza.cli.lessons import LESSONS
from pefforza.constants import COLS, ROWS

if TYPE_CHECKING:
    from pefforza.cli.play_gui import GameApp

WIDTH, HEIGHT = 1040, 820
CELL = 80
BOARD_X, BOARD_Y = 56, 228
BOARD_RECT = pygame.Rect(BOARD_X, BOARD_Y, COLS * CELL, ROWS * CELL)
BG = (17, 22, 34)
PANEL = (26, 33, 49)
EDGE = (48, 58, 78)
INK = (242, 241, 232)
MUTED = (161, 172, 190)
MINT = (179, 231, 203)
RED = (249, 132, 120)
YELLOW = (239, 205, 111)

BUTTONS = {
    "restart": pygame.Rect(688, 544, 296, 48),
    "undo": pygame.Rect(688, 604, 142, 44),
    "hint": pygame.Rect(842, 604, 142, 44),
    "difficulty": pygame.Rect(688, 414, 296, 48),
    "lessons": pygame.Rect(688, 660, 296, 44),
}

TIER_COPY = {
    "easy": ("A little warm-up", "Random moves. Room to experiment."),
    "medium": ("A sparring partner", "Spots wins, blocks threats, likes center."),
    "hard": ("Think a few moves ahead", "Depth-8 search. Bring your best ideas."),
    "impossible": ("Challenge the solver", "Time-limited proof, then a safe fallback."),
    "neural": ("Meet the student", "A trained PPO policy, still learning."),
}


def column_at(pos: tuple[int, int]) -> int | None:
    if pygame.Rect(BOARD_X, BOARD_Y - 48, COLS * CELL, ROWS * CELL + 48).collidepoint(pos):
        return (pos[0] - BOARD_X) // CELL
    return None


def cell_center(row: int, col: int) -> tuple[int, int]:
    return BOARD_X + col * CELL + CELL // 2, BOARD_Y + row * CELL + CELL // 2


def viewport(size: tuple[int, int]) -> pygame.Rect:
    scale = min(size[0] / WIDTH, size[1] / HEIGHT)
    width, height = max(1, int(WIDTH * scale)), max(1, int(HEIGHT * scale))
    return pygame.Rect((size[0] - width) // 2, (size[1] - height) // 2, width, height)


def map_pointer(event: pygame.event.Event, area: pygame.Rect) -> pygame.event.Event | None:
    if event.type not in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
        return event
    if not area.collidepoint(event.pos):
        return None
    attributes = event.dict.copy()
    attributes["pos"] = (
        (event.pos[0] - area.x) * WIDTH // area.width,
        (event.pos[1] - area.y) * HEIGHT // area.height,
    )
    return pygame.event.Event(event.type, attributes)


class GameView:
    def __init__(self) -> None:
        self.fonts = {
            size: pygame.font.SysFont(
                ["segoeui", "helveticaneue", "dejavusans", "arial"],
                size,
                bold=size in (22, 32, 42),
            )
            for size in (12, 14, 16, 18, 22, 32, 42)
        }

    def text(
        self,
        screen: pygame.Surface,
        value: str,
        pos: tuple[int, int],
        size: int = 16,
        color: tuple[int, int, int] = INK,
    ) -> None:
        screen.blit(self.fonts[size].render(value, True, color), pos)

    def wrapped(self, screen: pygame.Surface, value: str, x: int, y: int, width: int) -> None:
        line = ""
        for word in value.split():
            candidate = f"{line} {word}".strip()
            if self.fonts[14].size(candidate)[0] > width and line:
                self.text(screen, line, (x, y), 14, MUTED)
                y += 23
                line = word
            else:
                line = candidate
        self.text(screen, line, (x, y), 14, MUTED)

    def token(
        self, screen: pygame.Surface, player: int, center: tuple[int, int], radius: int = 29
    ) -> None:
        color = RED if player == 1 else YELLOW
        pygame.draw.circle(screen, tuple(int(v * 0.65) for v in color), center, radius)
        pygame.draw.circle(screen, color, (center[0], center[1] - 3), radius - 2)
        pygame.draw.circle(screen, tuple(int(v * 0.8) for v in color), center, radius - 10, 2)
        glyph = "X" if player == 1 else "O"
        label = self.fonts[16].render(glyph, True, BG)
        screen.blit(label, label.get_rect(center=center))

    def draw(self, screen: pygame.Surface, app: GameApp, now: int) -> None:
        game = app.session
        lesson = LESSONS[app.lesson_index] if app.lesson_index is not None else None
        screen.fill(BG)
        for i, color in enumerate((RED, YELLOW, MINT, INK)):
            pygame.draw.circle(screen, color, (48 + (i % 2) * 13, 42 + (i // 2) * 13), 5)
        self.text(screen, "PEFFORZA 4", (82, 32), 22)
        self.text(screen, "A SMALL GAME. A CURIOUS MIND.", (714, 40), 12, MUTED)
        pygame.draw.line(screen, EDGE, (40, 88), (1000, 88))
        self.text(screen, "Tiny tactics." if lesson else "Four in a row.", (48, 112), 42)
        self.text(screen, lesson.title if lesson else "One more round?", (50, 167), 18, MUTED)
        self.text(screen, "THE PLAYGROUND", (688, 126), 12, MINT)
        counter = (
            f"Lesson {app.lesson_index + 1:02d} / {len(LESSONS):02d}"
            if app.lesson_index is not None
            else f"Move {len(game.moves) + (not game.game_over):02d}"
        )
        self.text(screen, counter, (688, 153), 32)

        pygame.draw.rect(screen, (9, 13, 23), (42, 220, 588, 506), border_radius=28)
        pygame.draw.rect(screen, (38, 48, 72), (40, 212, 592, 508), border_radius=28)
        pygame.draw.rect(screen, (61, 74, 100), (40, 212, 592, 508), 1, border_radius=28)
        selected = app.hint_col if app.hint_col is not None else app.selected_col
        can_play = game.current_player == 1 and not game.game_over and app.animation is None
        if can_play and selected in range(COLS) and game.board[0, selected] == 0:
            pygame.draw.rect(
                screen,
                (46, 63, 82),
                (BOARD_X + selected * CELL + 5, BOARD_Y, CELL - 10, ROWS * CELL),
                border_radius=24,
            )

        winning = set(game.winning_cells)
        for row in range(ROWS):
            for col in range(COLS):
                center = cell_center(row, col)
                pygame.draw.circle(screen, (60, 71, 94), (center[0], center[1] + 2), 32)
                pygame.draw.circle(screen, BG, center, 32)
                player = int(game.board[row, col])
                if player:
                    self.token(screen, player, center)
                if (row, col) in winning:
                    pygame.draw.circle(screen, INK, center, 35, 3)
                elif game.moves and col == game.moves[-1] and player:
                    above_empty = row == 0 or game.board[row - 1, col] == 0
                    if above_empty:
                        pygame.draw.circle(screen, INK, (center[0] + 20, center[1] - 20), 4)

        if app.animation is not None:
            col, row, player, start = app.animation
            progress = min(1.0, (now - start) / app.animation_duration)
            x, end_y = cell_center(row, col)
            y = BOARD_Y - 28 + (end_y - BOARD_Y + 28) * progress**2
            self.token(screen, player, (x, round(y)))

        for col in range(COLS):
            x = cell_center(0, col)[0]
            active = can_play and col == selected and game.board[0, col] == 0
            color = MINT if active else MUTED
            label = self.fonts[14].render(str(col + 1), True, color)
            screen.blit(label, label.get_rect(center=(x, 746)))
            if active:
                pygame.draw.circle(screen, MINT, (x, 766), 3)

        pygame.draw.rect(screen, PANEL, (668, 212, 336, 170), border_radius=20)
        turn = "Your turn" if game.current_player == 1 else "Thinking" + "." * (now // 400 % 4)
        if game.game_over:
            turn = "You got four!" if game.winner == 1 else "AI got four."
            if not game.winner:
                turn = "A worthy draw."
        elif app.animation is not None:
            turn = "Nice drop." if app.animation[2] == 1 else "AI's move"
        if lesson and app.animation is None:
            turn = (
                "You found it!"
                if app.lesson_solved
                else "Try again"
                if app.lesson_attempted
                else "Your challenge"
            )
        self.text(screen, turn, (690, 234), 22, MINT)
        status = app.notice or game.status
        self.wrapped(screen, status, 690, 273, 292)
        self.text(screen, "X  YOU", (690, 343), 12, RED)
        self.text(screen, "O  AI", (875, 343), 12, YELLOW)

        self.text(screen, "KEEP EXPLORING" if lesson else "YOUR OPPONENT", (688, 393), 12, MUTED)
        for name, rect in BUTTONS.items():
            fill = MINT if name == "restart" else PANEL
            pygame.draw.rect(screen, fill, rect, border_radius=12)
            if name != "restart":
                pygame.draw.rect(screen, EDGE, rect, 1, border_radius=12)
        self.text(screen, "Next lesson" if lesson else app.opponent_label, (704, 427), 14)
        self.text(screen, "N / next" if lesson else "D / new round", (874, 430), 12, MUTED)
        copy = TIER_COPY[app.difficulty][1]
        if app.worker.active_difficulty != app.difficulty:
            copy = "Requested opponent unavailable. The active fallback is shown above."
        if lesson:
            copy = "One move, one idea. Retry freely; hints explain the answer."
        self.wrapped(screen, copy, 688, 477, 296)
        replay = "Try again" if lesson else "Play again" if game.game_over else "New round"
        self.text(screen, replay, (706, 557), 16, BG)
        self.text(screen, "R", (958, 560), 12, BG)
        self.text(screen, "Undo   U", (704, 617), 14)
        self.text(screen, "Hint   H", (862, 617), 14)
        self.text(screen, "Free play" if lesson else "Tactical lessons", (704, 673), 14)
        self.text(screen, "L", (958, 675), 12, MUTED)
        self.wrapped(
            screen, "Try a thought. Take it back. Find your next good move.", 688, 718, 296
        )
        pygame.draw.line(screen, EDGE, (40, 788), (1000, 788))
        self.text(screen, "CLICK A COLUMN  /  KEYS 1-7", (48, 799), 12, MUTED)
        self.text(screen, "ARROWS + ENTER TO DROP     ESC TO LEAVE", (678, 799), 12, MUTED)
