"""Export browser geometry and rule conformance cases from the Python source of truth.

Run from the repository root after installing Pefforza: python scripts/export_web_game.py.
The checked-in export allows the website to build independently with only Node.js.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from pefforza.constants import AI_PLAYER, COLS, EMPTY, HUMAN_PLAYER, ROWS, WIN_LENGTH
from pefforza.rules import available_columns, check_winner, empty_board, next_open_row


def main() -> None:
    target = Path(__file__).resolve().parents[1] / "website" / "lib"
    target.mkdir(parents=True, exist_ok=True)
    windows = []
    for dr, dc in [(0, 1), (1, 0), (1, 1), (-1, 1)]:
        for row in range(ROWS):
            for col in range(COLS):
                cells = [(row + i * dr, col + i * dc) for i in range(WIN_LENGTH)]
                if all(0 <= r < ROWS and 0 <= c < COLS for r, c in cells):
                    windows.append([r * COLS + c for r, c in cells])
    geometry = {
        "rows": ROWS,
        "cols": COLS,
        "winLength": WIN_LENGTH,
        "empty": EMPTY,
        "ai": AI_PLAYER,
        "human": HUMAN_PLAYER,
        "windows": windows,
    }
    (target / "geometry.json").write_text(json.dumps(geometry), encoding="utf-8")

    rng = random.Random(704)
    cases = []
    for _ in range(100):
        board = empty_board()
        player = HUMAN_PLAYER
        while True:
            legal = available_columns(board)
            winner = check_winner(board)
            cases.append({"board": board.ravel().tolist(), "legal": legal, "winner": winner})
            if winner or not legal:
                break
            col = rng.choice(legal)
            board[next_open_row(board, col), col] = player
            player = AI_PLAYER if player == HUMAN_PLAYER else HUMAN_PLAYER
    test_target = target.parent / "tests"
    test_target.mkdir(exist_ok=True)
    (test_target / "python-rules.json").write_text(json.dumps(cases), encoding="utf-8")
    print(f"Exported geometry and {len(cases)} Python rule conformance positions.")


if __name__ == "__main__":
    main()
