"""Check an installed wheel from outside the checkout with venv Python -I.

This distribution check deliberately loads the bundled model. Unit tests remain
independent of trained checkpoints, webcams, audio devices, and displays.
"""

from __future__ import annotations

import multiprocessing
import sys
import time
from pathlib import Path

import numpy as np

import pefforza
from pefforza.agent.difficulty import build_opponent
from pefforza.agent.evaluate import model_agent
from pefforza.cli.gui_game import GameSession, OpponentWorker
from pefforza.constants import COLS, DEFAULT_MODEL_PATH, ROWS
from pefforza.rules import available_columns, empty_board


def main() -> None:
    assert sys.flags.isolated, "Run this check with Python -I."
    assert sys.prefix != sys.base_prefix, "Use a dedicated wheel-test virtual environment."
    source = Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(source), "Run outside the checkout."
    package = Path(pefforza.__file__).resolve().parent
    assert package.is_relative_to(Path(sys.prefix).resolve()), package
    assert not package.is_relative_to(source / "pefforza"), package
    checkpoint = DEFAULT_MODEL_PATH.resolve()
    assert checkpoint.is_relative_to(package) and checkpoint.is_file(), checkpoint
    print(f"Installed package: {package}", flush=True)

    from stable_baselines3 import PPO

    model = PPO.load(str(checkpoint), device="cpu")
    board = empty_board()
    action, _ = model.predict(board, deterministic=True)
    prediction = np.asarray(action)
    assert prediction.size == 1 and np.issubdtype(prediction.dtype, np.integer), action
    column = int(prediction.item())
    assert column in available_columns(board), column
    assert model_agent(model)(board, 1, available_columns(board)) == column

    def reject_fallback(name: str) -> None:
        raise AssertionError(f"Unexpected neural model fallback: {name}")

    neural = build_opponent("neural", on_fallback=reject_fallback)
    assert neural(board, 1, available_columns(board)) == column
    print(f"Bundled checkpoint loaded and inferred column {column + 1}.", flush=True)

    # Exercise the installed controller and an actual spawned search worker.
    game = GameSession(seed=27)
    human = build_opponent("easy", seed=27)
    worker = OpponentWorker("hard", seed=13)
    worker_pid = None
    try:
        for _ in range(ROWS * COLS):
            valid = available_columns(game.board)
            if game.current_player == 1:
                move = human(game.board.copy(), 1, valid)
            else:
                worker.request(game.board, 2)
                assert worker._process is not None
                worker_pid = worker._process.pid
                deadline = time.monotonic() + 20
                move = worker.poll()
                while move is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                    move = worker.poll()
                assert move is not None, "Installed worker did not return a move."
                assert worker.error is None, worker.error
                assert worker.active_difficulty == "hard", worker.active_difficulty
            assert move in valid and game.play(move), move
            if game.game_over:
                break
        assert game.game_over, "Installed-package game did not terminate."
    finally:
        worker.close()
    assert worker._process is None
    assert worker_pid not in {child.pid for child in multiprocessing.active_children()}
    print(f"Installed search game finished in {len(game.moves)} moves; no fallback.", flush=True)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
