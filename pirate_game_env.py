import gymnasium as gym
import numpy as np
from gymnasium import spaces

from game_session import GameSession
from game_types import GameAction


class PirateGameEnv(gym.Env):
    metadata = {"render_modes": ["none", "human"], "render_fps": 30}

    def __init__(
        self,
        level_path: str = "level.txt",
        headless: bool = True,
        render_mode: str = "none",
        max_episode_steps: int = 2500,
        frame_skip: int = 4,
    ):
        super().__init__()
        self.level_path = level_path
        self.headless = headless
        self.render_mode = render_mode
        self.max_episode_steps = max_episode_steps
        self.frame_skip = frame_skip

        self.session = GameSession(
            level_path=self.level_path,
            headless=self.headless,
            render_mode=self.render_mode,
            fps=self.metadata["render_fps"],
        )

        self.action_space = spaces.Discrete(4)
        self.observation_space = spaces.Box(
            low=np.array([0.0, 0.0, -100.0, 0.0], dtype=np.float32),
            high=np.array([5000.0, 1200.0, 100.0, 5000.0], dtype=np.float32),
            dtype=np.float32,
        )
        self._episode_steps = 0

    def _to_action(self, action_id: int) -> GameAction:
        if action_id == 0:
            return GameAction(left=True)
        if action_id == 1:
            return GameAction(right=True)
        if action_id == 2:
            return GameAction(jump=True)
        return GameAction(shoot=True)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        level_path = self.level_path if options is None else options.get("level_path", self.level_path)
        obs = self.session.reset(level_path=level_path, seed=seed)
        self._episode_steps = 0
        return np.asarray(obs, dtype=np.float32), {}

    def step(self, action):
        game_action = self._to_action(int(action))
        result = self.session.step(game_action, frames=self.frame_skip)
        obs = np.asarray(result["observation"], dtype=np.float32)
        status = result["status"]

        terminated = bool(status["is_done"])
        self._episode_steps += 1
        truncated = self._episode_steps >= self.max_episode_steps and not terminated

        reward = 0.0
        if status["is_win"]:
            reward = 1.0
        elif status["is_dead"]:
            reward = -1.0

        info = {
            "killed_enemies": result["killed_enemies"],
            "is_win": status["is_win"],
            "is_dead": status["is_dead"],
            "step_count": status["step_count"],
            "max_progress_x": status["max_progress_x"],
        }
        return obs, reward, terminated, truncated, info

    def render(self):
        self.session.render()

    def close(self):
        self.session.close()
