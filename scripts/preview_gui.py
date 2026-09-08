"""Development browser view of the shared Python game controller."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import queue
import secrets
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pygame

from pefforza.cli.gui_view import HEIGHT, TIER_COPY, WIDTH, cell_center
from pefforza.cli.lessons import LESSONS
from pefforza.cli.play_gui import GameApp
from pefforza.constants import COLS, ROWS


def parse_event(payload: dict) -> pygame.event.Event:
    """Accept only the input primitives used by the preview page."""
    kind = payload.get("kind")
    if kind == "select":
        column = payload.get("column")
        if type(column) is not int or not 0 <= column < COLS:
            raise ValueError("Invalid column")
        return pygame.event.Event(pygame.MOUSEMOTION, pos=cell_center(0, column))
    if kind in ("click", "move"):
        x, y = payload["x"], payload["y"]
        if type(x) is not int or type(y) is not int or not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            raise ValueError("Invalid coordinates")
        event_type = pygame.MOUSEBUTTONDOWN if kind == "click" else pygame.MOUSEMOTION
        return pygame.event.Event(event_type, pos=(x, y), button=1)
    keys = {
        **{str(i): pygame.K_1 + i - 1 for i in range(1, 8)},
        "r": pygame.K_r,
        "u": pygame.K_u,
        "h": pygame.K_h,
        "d": pygame.K_d,
        "l": pygame.K_l,
        "n": pygame.K_n,
        "ArrowLeft": pygame.K_LEFT,
        "ArrowRight": pygame.K_RIGHT,
        "Enter": pygame.K_RETURN,
        " ": pygame.K_SPACE,
    }
    if kind == "key" and payload.get("key") in keys:
        return pygame.event.Event(pygame.KEYDOWN, key=keys[payload["key"]])
    raise ValueError("Unsupported input")


def snapshot(app: GameApp, now: int) -> dict:
    """One coherent state, including timing for browser-local interpolation.

    The board remains pre-drop until the controller commits the move. An
    animation's start tick is its identity; repeated snapshots must not restart it.
    """
    game = app.session
    lesson = LESSONS[app.lesson_index] if app.lesson_index is not None else None
    animation = None
    if app.animation is not None:
        column, row, player, start = app.animation
        animation = {
            "id": start,
            "column": column,
            "row": row,
            "player": player,
            "duration": app.animation_duration,
            "elapsed": max(0, now - start),
        }
    return {
        "rows": ROWS,
        "columns": COLS,
        "moves": len(game.moves),
        "board": game.board.tolist(),
        "player": game.current_player,
        "gameOver": game.game_over,
        "winner": game.winner,
        "winningCells": game.winning_cells,
        "difficulty": app.opponent_label,
        "opponentCopy": (
            TIER_COPY[app.difficulty][1]
            if app.worker.active_difficulty == app.difficulty
            else "Requested opponent unavailable. The active fallback is shown above."
        ),
        "lesson": app.lesson_index,
        "lessonTitle": lesson.title if lesson else None,
        "lessonCount": len(LESSONS),
        "lessonSolved": app.lesson_solved,
        "lessonAttempted": app.lesson_attempted,
        "selectedColumn": app.hint_col if app.hint_col is not None else app.selected_col,
        "status": app.notice or game.status,
        "animation": animation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()
    token = secrets.token_urlsafe(24)
    page = (
        Path(__file__)
        .with_name("preview_gui.html")
        .read_text(encoding="utf-8")
        .replace("__TOKEN__", token)
    )
    javascript = Path(__file__).with_name("preview_gui.mjs").read_bytes()
    inputs: queue.Queue[pygame.event.Event] = queue.Queue(maxsize=64)
    state = b"{}"

    class Handler(BaseHTTPRequestHandler):
        def respond(self, code: int, content: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            with contextlib.suppress(ConnectionError):
                self.wfile.write(content)

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/":
                self.respond(200, page.encode(), "text/html; charset=utf-8")
            elif path == "/preview_gui.mjs":
                self.respond(200, javascript, "text/javascript; charset=utf-8")
            elif path == "/state":
                self.respond(200, state, "application/json")
            else:
                self.respond(404, b"Not found", "text/plain")

        def do_POST(self) -> None:
            if self.path != "/event" or self.headers.get("X-Preview-Token") != token:
                self.respond(403, b"Forbidden", "text/plain")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024:
                    raise ValueError("Invalid payload length")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Expected input object")
                inputs.put_nowait(parse_event(payload))
            except (ValueError, KeyError, TypeError, queue.Full):
                self.respond(400, b"Invalid input", "text/plain")
                return
            self.respond(204, b"", "text/plain")

        def log_message(self, format: str, *args: object) -> None:
            pass

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    app = GameApp(seed=4)
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, lambda *_: setattr(app, "running", False))
    state = json.dumps(snapshot(app, pygame.time.get_ticks())).encode()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Pefforza browser preview on http://{args.host}:{args.port}", flush=True)
    clock = pygame.time.Clock()
    try:
        while app.running:
            now = pygame.time.get_ticks()
            for event in pygame.event.get():
                app.handle_event(event, now)
            for _ in range(64):
                try:
                    event = inputs.get_nowait()
                except queue.Empty:
                    break
                app.handle_event(event, now)
            app.tick(now)
            state = json.dumps(snapshot(app, now)).encode()
            clock.tick(60)
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
        server.shutdown()
        server.server_close()
        pygame.quit()


if __name__ == "__main__":
    main()
