"""Gymnasium environment for Connect 4.

Observations use absolute player IDs (1 and 2); ``current_player`` identifies
whose turn it is. Wrap with :class:`pefforza.agent.train.SinglePlayerWrapper`
(or any opponent policy) when training a single agent against an opponent.

Public behavior preserved from the original implementation:
* Reward of +1 on win, 0 on draw, 0 per non-terminal move.
* Invalid moves return reward -10 and terminate the episode (kept so that
  trained checkpoints stay usable; entrypoints should pre-validate moves).
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from pefforza.constants import COLS, EMPTY, ROWS
from pefforza.rules import (
    Board,
    check_winner,
    empty_board,
    is_board_full,
    is_column_full,
    next_open_row,
)

INVALID_MOVE_PENALTY: float = -10.0
WIN_REWARD: float = 1.0
STEP_REWARD: float = 0.0


class Connect4Env(gym.Env):
    """Two-player Connect 4 board, single-agent observation."""

    metadata = {"render_modes": ["human", "rgb_array"]}

    def __init__(self, render_mode: str | None = None) -> None:
        super().__init__()
        if render_mode is not None and render_mode not in self.metadata["render_modes"]:
            raise ValueError(f"Unsupported render mode: {render_mode}")

        self.rows = ROWS
        self.cols = COLS

        self.observation_space = spaces.Box(
            low=0, high=2, shape=(self.rows, self.cols), dtype=np.int8
        )
        self.action_space = spaces.Discrete(self.cols)

        self.render_mode = render_mode
        self.board: Board = empty_board()
        self.current_player: int = 1
        self._terminated = False

    # ------------------------------------------------------------------ API
    def reset(
        self,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[Board, dict[str, Any]]:
        super().reset(seed=seed)
        self.board = empty_board()
        self.current_player = 1
        self._terminated = False
        return self.board.copy(), {}

    def step(self, action: int) -> tuple[Board, float, bool, bool, dict[str, Any]]:
        if self._terminated:
            raise RuntimeError("Episode has ended; call reset() before stepping again")
        if isinstance(action, (bool, np.bool_)) or not self.action_space.contains(action):
            self._terminated = True
            return (
                self.board.copy(),
                INVALID_MOVE_PENALTY,
                True,
                False,
                {"error": "Action out of range"},
            )
        action = int(action)
        if is_column_full(self.board, action):
            self._terminated = True
            return self.board.copy(), INVALID_MOVE_PENALTY, True, False, {"error": "Invalid move"}

        row = next_open_row(self.board, action)
        self.board[row, action] = self.current_player

        winner = check_winner(self.board)
        if winner == self.current_player:
            self._terminated = True
            return self.board.copy(), WIN_REWARD, True, False, {"winner": winner}

        if is_board_full(self.board):
            self._terminated = True
            return self.board.copy(), STEP_REWARD, True, False, {"draw": True}

        # Hand turn over to the other player.
        self.current_player = 3 - self.current_player
        return self.board.copy(), STEP_REWARD, False, False, {}

    # ------------------------------------------------------------------ misc
    def valid_action_mask(self) -> np.ndarray:
        """Boolean mask of legal moves; useful for action masking wrappers."""
        if self._terminated:
            return np.zeros(self.cols, dtype=bool)
        return np.array(
            [self.board[0, c] == EMPTY for c in range(self.cols)],
            dtype=bool,
        )

    def render(self) -> np.ndarray | None:
        if self.render_mode == "human":
            print("----------------")
            print(self.board)
            print("----------------")
        elif self.render_mode == "rgb_array":
            cell_size = 32
            palette = np.array([(17, 22, 34), (249, 132, 120), (239, 205, 111)], dtype=np.uint8)
            pixels = np.repeat(np.repeat(palette[self.board], cell_size, axis=0), cell_size, axis=1)
            y, x = np.ogrid[: ROWS * cell_size, : COLS * cell_size]
            outside = (x % cell_size - 16) ** 2 + (y % cell_size - 16) ** 2 > 13**2
            pixels[outside] = (38, 48, 72)
            return pixels
        return None
