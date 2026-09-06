"""Development-only browser remote for the real Pygame app (one shared game)."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import queue
import secrets
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pygame

from pefforza.cli.gui_view import HEIGHT, WIDTH, GameView
from pefforza.cli.play_gui import GameApp


def parse_event(payload: dict) -> pygame.event.Event:
    """Accept only the input primitives used by the preview page."""
    kind = payload.get("kind")
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
        "ArrowLeft": pygame.K_LEFT,
        "ArrowRight": pygame.K_RIGHT,
        "Enter": pygame.K_RETURN,
        " ": pygame.K_SPACE,
    }
    if kind == "key" and payload.get("key") in keys:
        return pygame.event.Event(pygame.KEYDOWN, key=keys[payload["key"]])
    raise ValueError("Unsupported input")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()
    token = secrets.token_urlsafe(24)
    page = Path(__file__).with_name("preview_gui.html").read_text().replace("__TOKEN__", token)
    inputs: queue.Queue[pygame.event.Event] = queue.Queue(maxsize=64)
    frame = b""
    state = b"{}"

    class Handler(BaseHTTPRequestHandler):
        def respond(self, code: int, content: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                self.wfile.write(content)

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/":
                self.respond(200, page.encode(), "text/html; charset=utf-8")
            elif path == "/frame.png":
                self.respond(200 if frame else 503, frame, "image/png")
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
    pygame.font.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    app = GameApp(seed=4)
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, lambda *_: setattr(app, "running", False))
    view = GameView()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Pygame development preview on http://{args.host}:{args.port}", flush=True)
    clock = pygame.time.Clock()
    last_frame = -100
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
            if now - last_frame >= 66:
                view.draw(screen, app, now)
                output = io.BytesIO()
                pygame.image.save(screen, output, "frame.png")
                frame = output.getvalue()
                state = json.dumps(
                    {
                        "moves": len(app.session.moves),
                        "board": app.session.board.tolist(),
                        "player": app.session.current_player,
                        "gameOver": app.session.game_over,
                        "winner": app.session.winner,
                        "difficulty": app.difficulty,
                        "status": app.notice or app.session.status,
                    }
                ).encode()
                last_frame = now
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
