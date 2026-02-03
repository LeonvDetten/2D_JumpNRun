from dataclasses import dataclass


@dataclass
class GameAction:
    left: bool = False
    right: bool = False
    jump: bool = False
    shoot: bool = False


@dataclass
class EpisodeStatus:
    is_win: bool = False
    is_dead: bool = False
    is_done: bool = False
    step_count: int = 0
    max_progress_x: float = 0.0
