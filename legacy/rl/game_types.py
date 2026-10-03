"""Shared data types used by the RL game session and Gym environment."""

from dataclasses import dataclass


@dataclass
class GameAction:
    """Discrete action mapped into game input buttons for one RL step."""

    left: bool = False
    right: bool = False
    jump: bool = False
    shoot: bool = False


@dataclass
class EpisodeStatus:
    """Minimal episode status used by the environment for termination and metrics."""

    is_win: bool = False
    is_dead: bool = False
    is_done: bool = False
    step_count: int = 0
    max_progress_x: float = 0.0
