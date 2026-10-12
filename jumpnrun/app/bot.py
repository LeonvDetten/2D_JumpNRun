"""The bot as an opponent: loads the best model in the background, races frame by frame next to the player.

PyTorch / stable-baselines3 are optional for the game - without them the "against the bot" mode is disabled.
"""

from __future__ import annotations

import threading
from typing import Optional

import numpy as np

from jumpnrun.core.actions import BOT_ACTIONS_V3
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Simulation, Status

RESPAWN_FRAMES = 30  # 1 s at the start again after a death (same rule as for the player)


class BotBrain:
    """Loads the representative bot (models/space_pirate_bot.zip) in a thread."""

    def __init__(self):
        self.model = None
        self.error: Optional[str] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is None and self.error is None:
            self._thread = threading.Thread(target=self._load, daemon=True)
            self._thread.start()

    def _load(self) -> None:
        try:
            import importlib

            import torch

            importlib.import_module("stable_baselines3")
        except ImportError:
            self.error = "Für den Bot fehlt PyTorch: pip install torch stable-baselines3 gymnasium"
            return
        try:
            from jumpnrun.rl.modelinfo import BEST_MODEL, load_for_play

            torch.set_num_threads(1)  # one small net, no need to fight the game for CPU
            self.model = load_for_play(BEST_MODEL)
        except Exception as exc:  # pragma: no cover - shown in the menu
            self.error = f"Bot konnte nicht geladen werden: {type(exc).__name__}: {exc}"

    @property
    def ready(self) -> bool:
        return self.model is not None

    @property
    def loading(self) -> bool:
        return self.model is None and self.error is None and self._thread is not None

    def wait(self, timeout: Optional[float] = None) -> bool:
        if self._thread is not None:
            self._thread.join(timeout)
        return self.ready


class BotRacer:
    """One bot in a race: plays the level with the trained policy, frame by frame."""

    def __init__(self, model, level: Level, delay_frames: int = 0, temperature: Optional[float] = None):
        from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
        from jumpnrun.rl.modelinfo import PLAY_TEMPERATURE, env_kwargs

        self.model = model
        self.temperature = PLAY_TEMPERATURE if temperature is None else temperature
        self.env = JumpNRunEnv(fixed_levels([level]), **env_kwargs(model))
        self.repeat = self.env.action_repeat
        self.wait = delay_frames
        self.respawn = 0
        self.deaths = 0
        self.finish_frame: Optional[int] = None  # race frame when the bot reached the chest
        self.frame = 0  # race frames since the start signal
        self._restart()

    def _restart(self) -> None:
        self.obs, _ = self.env.reset(seed=self.deaths)
        self.k = 0
        self.action = 0
        self.before = self.env.sim.max_x

    @property
    def sim(self) -> Simulation:
        return self.env.sim

    @property
    def visible(self) -> bool:
        return self.wait <= 0 and self.respawn == 0

    @property
    def won(self) -> bool:
        return self.finish_frame is not None

    def step(self) -> Optional[str]:
        """One game frame. Returns an event: 'won', 'died' or None."""

        self.frame += 1
        if self.won:
            return None
        if self.wait > 0:
            self.wait -= 1
            return None
        if self.respawn > 0:
            self.respawn -= 1
            if self.respawn == 0:
                self._restart()
            return None
        if self.k == 0:
            from jumpnrun.rl.modelinfo import choose_actions

            batch = {key: np.expand_dims(value, 0) for key, value in self.obs.items()}
            self.action = int(choose_actions(self.model, batch, temperature=self.temperature)[0])
            self.before = self.sim.max_x
        self.sim.step(BOT_ACTIONS_V3[self.action])
        self.k += 1
        if self.sim.status == Status.WON:
            self.finish_frame = self.frame
            return "won"
        if self.k < self.repeat and self.sim.status == Status.RUNNING:
            return None
        self.k = 0
        self.obs, _, terminated, truncated, _ = self.env.finish_step(self.action, self.before)
        if self.sim.status in (Status.DIED_PIT, Status.DIED_ENEMY) or terminated or truncated:
            self.deaths += 1
            self.respawn = RESPAWN_FRAMES  # died, or stuck for too long: back to the start
            return "died"
        return None
