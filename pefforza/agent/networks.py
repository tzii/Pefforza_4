"""Neural network building blocks for the ``neural`` tier.

:class:`Connect4CNN` is a Stable-Baselines3 features extractor, so policies
built with it are ordinary SB3 ``PPO`` checkpoints: ``PPO.load`` restores
them as long as :mod:`pefforza` is importable (the class is stored by
reference in the zip).
"""

from __future__ import annotations

import gymnasium as gym
import torch
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from torch import nn

from pefforza.constants import COLS, ROWS


class Connect4CNN(BaseFeaturesExtractor):
    """Convolutional trunk over one-hot board planes.

    The observation is the 6x7 board from the mover's perspective
    (0 empty, 1 self, 2 opponent). It is split into three binary planes
    (self, opponent, empty), passed through ``blocks`` 3x3 convolutions that
    keep the board size - four-in-a-row patterns are local, which is exactly
    what convolutions see - then squeezed by a 1x1 convolution and projected
    to ``features_dim``.
    """

    def __init__(
        self,
        observation_space: gym.spaces.Box,
        features_dim: int = 256,
        channels: int = 64,
        blocks: int = 4,
        head_channels: int = 16,
    ) -> None:
        super().__init__(observation_space, features_dim)
        layers: list[nn.Module] = [nn.Conv2d(3, channels, 3, padding=1), nn.ReLU()]
        for _ in range(blocks - 1):
            layers += [nn.Conv2d(channels, channels, 3, padding=1), nn.ReLU()]
        layers += [nn.Conv2d(channels, head_channels, 1), nn.ReLU(), nn.Flatten()]
        self.trunk = nn.Sequential(*layers)
        self.project = nn.Sequential(
            nn.Linear(head_channels * ROWS * COLS, features_dim), nn.ReLU()
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        board = observations.reshape(-1, ROWS, COLS)
        planes = torch.stack((board == 1, board == 2, board == 0), dim=1).float()
        return self.project(self.trunk(planes))


__all__ = ["Connect4CNN"]
