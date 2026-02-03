import gymnasium as gym
import numpy as np
from gymnasium import spaces

from rl.game_session import GameSession
from rl.game_types import GameAction


class PirateGameEnv(gym.Env):
    metadata = {"render_modes": ["none", "human"], "render_fps": 30}

    def __init__(
        self,
        level_path: str = "level.txt",
        headless: bool = True,
        render_mode: str = "none",
        max_episode_steps: int = 2500,
        frame_skip: int = 4,
        action_preset: str = "simple",
    ):
        super().__init__()
        self.level_path = level_path
        self.headless = headless
        self.render_mode = render_mode
        self.max_episode_steps = max_episode_steps
        self.frame_skip = frame_skip
        self.action_preset = action_preset

        self.session = GameSession(
            level_path=self.level_path,
            headless=self.headless,
            render_mode=self.render_mode,
            fps=self.metadata["render_fps"],
            max_episode_steps=self.max_episode_steps,
        )

        action_count = 5 if self.action_preset == "simple" else 9
        self.action_space = spaces.Discrete(action_count)
        self.observation_space = spaces.Box(
            low=np.array(
                [
                    0.0,
                    0.0,
                    -1.0,
                    -1.0,
                    0.0,
                    -1.0,
                    -1.0,
                    -1.0,
                    -1.0,
                    -1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ],
                dtype=np.float32,
            ),
            high=np.array(
                [
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                ],
                dtype=np.float32,
            ),
            dtype=np.float32,
        )
        self._episode_steps = 0
        self._no_progress_steps = 0
        self._prev_x = 0.0
        self._prev_goal_distance = 0.0
        self._max_checkpoint_reached = 0
        self.checkpoint_spacing = 600.0
        self.checkpoint_bonus = 3.0

    def _simple_action(self, action_id: int) -> GameAction:
        if action_id == 0:
            return GameAction()
        if action_id == 1:
            return GameAction(left=True)
        if action_id == 2:
            return GameAction(right=True)
        if action_id == 3:
            return GameAction(jump=True)
        return GameAction(right=True, jump=True)

    def _to_action(self, action_id: int) -> GameAction:
        if self.action_preset == "simple":
            return self._simple_action(action_id)

        if action_id == 0:
            return GameAction()
        if action_id == 1:
            return GameAction(left=True)
        if action_id == 2:
            return GameAction(right=True)
        if action_id == 3:
            return GameAction(jump=True)
        if action_id == 4:
            return GameAction(left=True, jump=True)
        if action_id == 5:
            return GameAction(right=True, jump=True)
        if action_id == 6:
            return GameAction(shoot=True)
        if action_id == 7:
            return GameAction(left=True, shoot=True)
        return GameAction(right=True, shoot=True)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        level_path = self.level_path if options is None else options.get("level_path", self.level_path)
        obs = self.session.reset(level_path=level_path, seed=seed)
        self._episode_steps = 0
        self._no_progress_steps = 0
        self._prev_x = float(self.session.player.playerPos.x)
        self._prev_goal_distance = float(self.session.get_goal_distance())
        self._max_checkpoint_reached = int(float(self.session.player.playerPos.x) // self.checkpoint_spacing)
        return np.asarray(obs, dtype=np.float32), {}

    def step(self, action):
        game_action = self._to_action(int(action))
        result = self.session.step(game_action, frames=self.frame_skip)
        obs = np.asarray(result["observation"], dtype=np.float32)
        status = result["status"]
        level_width, level_height = self.session.get_level_size()

        terminated = bool(status["is_win"] or status["is_dead"] or status["is_done"])
        self._episode_steps += 1
        truncated = self._episode_steps >= self.max_episode_steps and not terminated

        current_x = float(result["current_x"])
        current_y = float(result["current_y"])
        delta_x = float(result["delta_x"])
        goal_distance = float(self.session.get_goal_distance())
        goal_delta = self._prev_goal_distance - goal_distance
        current_checkpoint = int(float(status["max_progress_x"]) // self.checkpoint_spacing)
        new_checkpoints = max(0, current_checkpoint - self._max_checkpoint_reached)
        checkpoint_reward = float(new_checkpoints) * self.checkpoint_bonus
        if new_checkpoints > 0:
            self._max_checkpoint_reached = current_checkpoint

        goal_progress_reward = float(np.clip(np.tanh(goal_delta / 45.0) * 1.5, -1.5, 1.5))
        time_penalty = -0.01
        kill_bonus = float(result["killed_enemies"]) * 1.0
        reward = float(goal_progress_reward + time_penalty + kill_bonus + checkpoint_reward)

        if goal_delta <= 1.0:
            self._no_progress_steps += 1
        else:
            self._no_progress_steps = 0
        if self._no_progress_steps >= 90:
            reward -= 0.6

        is_runaway = (
            current_x < -120.0
            or current_x > (level_width + 120.0)
            or current_y < -240.0
            or current_y > (level_height + 300.0)
        )
        if is_runaway and not terminated:
            terminated = True
            reward -= 120.0

        if status["is_win"]:
            reward += 260.0
        elif status["is_dead"]:
            reward -= 130.0
        elif truncated:
            reward -= 25.0

        self._prev_x = current_x
        self._prev_goal_distance = goal_distance

        info = {
            "killed_enemies": result["killed_enemies"],
            "is_win": status["is_win"],
            "is_dead": status["is_dead"] or bool(is_runaway),
            "step_count": status["step_count"],
            "max_progress_x": status["max_progress_x"],
            "current_x": current_x,
            "current_y": current_y,
            "delta_x": delta_x,
            "no_progress_steps": self._no_progress_steps,
            "goal_distance": goal_distance,
            "goal_delta": goal_delta,
            "checkpoint_index": self._max_checkpoint_reached,
            "reward_goal_progress": float(goal_progress_reward),
            "reward_checkpoint": checkpoint_reward,
            "reward_time": time_penalty,
            "reward_kill_bonus": kill_bonus,
            "is_runaway": bool(is_runaway),
        }
        return obs, reward, terminated, truncated, info

    def render(self):
        self.session.render()

    def close(self):
        self.session.close()
