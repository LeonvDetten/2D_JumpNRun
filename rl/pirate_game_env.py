"""Gymnasium environment wrapper around the custom 2D Jump'n'Run game."""

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from rl.game_session import GameSession
from rl.game_types import GameAction


class PirateGameEnv(gym.Env):
    """Stable-Baselines3 compatible environment using handcrafted feature observations."""

    metadata = {"render_modes": ["none", "human"], "render_fps": 30}

    def __init__(
        self,
        level_path: str = "level.txt",
        headless: bool = True,
        render_mode: str = "none",
        max_episode_steps: int = 2500,
        frame_skip: int = 2,
        action_preset: str = "simple",
        obs_profile: str = "balanced",
    ):
        super().__init__()
        self.level_path = level_path
        self.headless = headless
        self.render_mode = render_mode
        self.max_episode_steps = max_episode_steps
        self.frame_skip = frame_skip
        self.action_preset = action_preset
        self.obs_profile = obs_profile

        self.session = GameSession(
            level_path=self.level_path,
            headless=self.headless,
            render_mode=self.render_mode,
            fps=self.metadata["render_fps"],
            max_episode_steps=self.max_episode_steps,
            obs_profile=self.obs_profile,
        )

        if self.action_preset == "forward":
            action_count = 3
        elif self.action_preset == "simple":
            action_count = 5
        else:
            action_count = 9
        self.action_space = spaces.Discrete(action_count)
        # Observation bounds stay stable so old checkpoints remain loadable.
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
        self._prev_hazard_ahead_short = 0.0
        self._hazard_events = 0
        self._hazard_reactions = 0
        self._hazard_ignores = 0
        self._hazard_camp_steps = 0
        self._last_hazard_reward_zone = -1
        self._jump_actions = 0
        self.checkpoint_spacing = 600.0
        self.checkpoint_bonus = 3.0
        self.hazard_zone_width = 120.0
        self.hazard_forward_progress_threshold = 12.0
        self.hazard_response_bonus = 0.20
        self.hazard_ignore_step_penalty = -0.03
        self.hazard_ignore_death_penalty = -0.5
        self.hazard_backtrack_penalty = 0.0
        self.hazard_camp_penalty = 0.0
        self.hazard_camp_step_threshold = 6
        self.jump_in_place_dx_threshold = 6.0
        self.jump_in_place_penalty = 0.0
        self.no_progress_soft_steps = 90
        self.no_progress_hard_steps = 140
        self.no_progress_soft_penalty = -0.15
        self.no_progress_hard_penalty = -0.35
        self.no_progress_terminate_steps = 120
        self.no_progress_terminate_penalty = -20.0

    def _forward_action(self, action_id: int) -> GameAction:
        if action_id == 0:
            return GameAction()
        if action_id == 1:
            return GameAction(right=True)
        return GameAction(right=True, jump=True)

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
        if self.action_preset == "forward":
            return self._forward_action(action_id)

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
        self._prev_hazard_ahead_short = float(obs[10]) if self.obs_profile == "balanced" and len(obs) > 10 else 0.0
        self._hazard_events = 0
        self._hazard_reactions = 0
        self._hazard_ignores = 0
        self._hazard_camp_steps = 0
        self._last_hazard_reward_zone = -1
        self._jump_actions = 0
        return np.asarray(obs, dtype=np.float32), {}

    def step(self, action):
        game_action = self._to_action(int(action))
        jump_taken = bool(getattr(game_action, "jump", False))
        if jump_taken:
            self._jump_actions += 1

        result = self.session.step(game_action, frames=self.frame_skip)
        obs = np.asarray(result["observation"], dtype=np.float32)
        status = result["status"]
        level_width, level_height = self.session.get_level_size()

        terminated = bool(status["is_win"] or status["is_dead"] or status["is_done"])
        self._episode_steps += 1
        truncated = self._episode_steps >= self.max_episode_steps and not terminated
        stagnation_truncated = False

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

        # Base shaping: encourage measurable progress and sparse milestone rewards.
        goal_progress_reward = float(np.clip(np.tanh(goal_delta / 45.0) * 1.5, -1.5, 1.5))
        time_penalty = -0.01
        kill_bonus = float(result["killed_enemies"]) * 1.0
        reward = float(goal_progress_reward + time_penalty + kill_bonus + checkpoint_reward)

        # Penalize repeated jumping with almost no horizontal movement.
        jump_in_place_penalty = 0.0
        if jump_taken and abs(delta_x) <= self.jump_in_place_dx_threshold and not status["is_win"]:
            jump_in_place_penalty = self.jump_in_place_penalty
            reward += jump_in_place_penalty

        if goal_delta <= 1.0:
            self._no_progress_steps += 1
        else:
            self._no_progress_steps = 0
        no_progress_penalty = 0.0
        if self._no_progress_steps >= self.no_progress_hard_steps:
            no_progress_penalty = self.no_progress_hard_penalty
        elif self._no_progress_steps >= self.no_progress_soft_steps:
            no_progress_penalty = self.no_progress_soft_penalty
        reward += no_progress_penalty
        if self._no_progress_steps >= self.no_progress_terminate_steps and not terminated:
            stagnation_truncated = not truncated
            truncated = True

        is_runaway = (
            current_x < -120.0
            or current_x > (level_width + 120.0)
            or current_y < -240.0
            or current_y > (level_height + 300.0)
        )
        if is_runaway and not terminated:
            terminated = True
            terminal_reward = -120.0
        else:
            terminal_reward = 0.0

        is_dead = bool(status["is_dead"]) or bool(is_runaway)

        if status["is_win"]:
            terminal_reward += 260.0
        elif is_dead:
            terminal_reward -= 130.0
        elif truncated:
            terminal_reward -= 25.0
        if stagnation_truncated:
            terminal_reward += self.no_progress_terminate_penalty
        reward += terminal_reward

        # Optional balanced-profile shaping for better reactivity near immediate hazards.
        hazard_response_reward = 0.0
        hazard_camp_penalty = 0.0
        hazard_zone = -1
        if self.obs_profile == "balanced":
            hazard_ahead_short_before = self._prev_hazard_ahead_short >= 0.5
            if hazard_ahead_short_before:
                self._hazard_events += 1
                hazard_zone = int(max(0.0, current_x) // self.hazard_zone_width)
                made_forward_progress = (
                    delta_x >= self.hazard_forward_progress_threshold and goal_delta > 0.0
                )
                can_reward_zone = hazard_zone != self._last_hazard_reward_zone
                if jump_taken and made_forward_progress and not is_dead and can_reward_zone:
                    self._hazard_reactions += 1
                    hazard_response_reward += self.hazard_response_bonus
                    self._last_hazard_reward_zone = hazard_zone
                    self._hazard_camp_steps = max(0, self._hazard_camp_steps - 2)
                else:
                    self._hazard_ignores += 1
                    hazard_response_reward += self.hazard_ignore_step_penalty
                    if abs(delta_x) <= 2.0:
                        self._hazard_camp_steps += 1
                    else:
                        self._hazard_camp_steps = max(0, self._hazard_camp_steps - 1)
                    if self._hazard_camp_steps >= self.hazard_camp_step_threshold:
                        hazard_camp_penalty += self.hazard_camp_penalty
                    if delta_x < -2.0:
                        hazard_camp_penalty += self.hazard_backtrack_penalty
                    if is_dead:
                        hazard_response_reward += self.hazard_ignore_death_penalty
            else:
                self._hazard_camp_steps = 0
        reward += hazard_response_reward + hazard_camp_penalty

        self._prev_x = current_x
        self._prev_goal_distance = goal_distance
        self._prev_hazard_ahead_short = float(obs[10]) if self.obs_profile == "balanced" and len(obs) > 10 else 0.0

        jump_rate = float(self._jump_actions / max(1, self._episode_steps))
        hazard_ignore_rate = float(self._hazard_ignores / max(1, self._hazard_events))
        hazard_reaction_rate = float(self._hazard_reactions / max(1, self._hazard_events))

        info = {
            "killed_enemies": result["killed_enemies"],
            "is_win": status["is_win"],
            "is_dead": is_dead,
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
            "reward_jump_in_place": float(jump_in_place_penalty),
            "reward_no_progress": float(no_progress_penalty),
            "reward_terminal": float(terminal_reward),
            "reward_hazard_response": float(hazard_response_reward),
            "reward_hazard_camp": float(hazard_camp_penalty),
            "jump_taken": int(jump_taken),
            "jump_rate": jump_rate,
            "hazard_events": int(self._hazard_events),
            "hazard_ignores": int(self._hazard_ignores),
            "hazard_reactions": int(self._hazard_reactions),
            "hazard_camp_steps": int(self._hazard_camp_steps),
            "hazard_zone": int(hazard_zone),
            "hazard_ignore_rate": hazard_ignore_rate,
            "hazard_reaction_rate": hazard_reaction_rate,
            "hazard_ahead_short": float(obs[10]) if self.obs_profile == "balanced" else 0.0,
            "hazard_ahead_mid": float(obs[11]) if self.obs_profile == "balanced" else 0.0,
            "enemy_threat_ahead": float(obs[12]) if self.obs_profile == "balanced" else 0.0,
            "enemy_threat_behind": float(obs[13]) if self.obs_profile == "balanced" else 0.0,
            "is_runaway": bool(is_runaway),
            "is_stagnation_truncated": bool(stagnation_truncated),
        }
        return obs, reward, terminated, truncated, info

    def render(self):
        self.session.render()

    def close(self):
        self.session.close()
