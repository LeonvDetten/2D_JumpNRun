"""Neural network that turns an observation into features for PPO.

    grid (4 x 13 x 25) -> small CNN  --\
                                        concat -> 256 features -> policy head (6 actions)
    vec  (15)          -> small MLP  --/                       -> value head  (expected reward)

The CNN slides the same 3x3 filters over the whole view, so a pattern like
"edge of a pit two tiles ahead" is recognised wherever it appears - that is
what lets the bot handle levels it has never seen.

Phase 6 adds an optional third input, the coarse `overview` map (4 x 13 x 32):

    overview -> small CNN -> 64 -> linear (starts at zero) --+--> added before the head's ReLU

The new linear layer starts with all weights zero, so a phase-5 network with this
branch attached ("network surgery") behaves exactly like before and only
gradually learns to use the far view.
"""

from __future__ import annotations

import gymnasium as gym
import torch
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from torch import nn


class GridFeatures(BaseFeaturesExtractor):
    def __init__(self, observation_space: gym.spaces.Dict, features_dim: int = 256):
        super().__init__(observation_space, features_dim)
        channels, rows, cols = observation_space["grid"].shape
        vec_size = observation_space["vec"].shape[0]
        self.cnn = nn.Sequential(
            nn.Conv2d(channels, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.Flatten(),
        )
        with torch.no_grad():
            cnn_out = self.cnn(torch.zeros(1, channels, rows, cols)).shape[1]
        self.vec_mlp = nn.Sequential(nn.Linear(vec_size, 64), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(cnn_out + 64, features_dim), nn.ReLU())
        self.has_overview = "overview" in observation_space.spaces
        if self.has_overview:
            ov_channels, ov_rows, ov_cols = observation_space["overview"].shape
            self.ov_cnn = nn.Sequential(
                nn.Conv2d(ov_channels, 16, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv2d(16, 32, kernel_size=3, stride=2, padding=1),
                nn.ReLU(),
                nn.Flatten(),
            )
            with torch.no_grad():
                ov_out = self.ov_cnn(torch.zeros(1, ov_channels, ov_rows, ov_cols)).shape[1]
            self.ov_mlp = nn.Sequential(nn.Linear(ov_out, 64), nn.ReLU())
            self.ov_head = nn.Linear(64, features_dim)
            self.zero_overview_output()

    def zero_overview_output(self) -> None:
        """Silence the overview branch (SB3 re-initialises all layers, so this is called again after surgery)."""

        nn.init.zeros_(self.ov_head.weight)
        nn.init.zeros_(self.ov_head.bias)

    def forward(self, observations):
        grid = self.cnn(observations["grid"])
        vec = self.vec_mlp(observations["vec"])
        if not self.has_overview:
            return self.head(torch.cat([grid, vec], dim=1))
        pre = self.head[0](torch.cat([grid, vec], dim=1))
        pre = pre + self.ov_head(self.ov_mlp(self.ov_cnn(observations["overview"])))
        return torch.relu(pre)
