"""Player input for one frame - produced by the keyboard (human) or by the bot."""

from __future__ import annotations

from typing import NamedTuple


class Action(NamedTuple):
    left: bool = False
    right: bool = False
    jump: bool = False
    shoot: bool = False


NOOP = Action()

# The discrete action set of the bot (index -> Action). The level solver uses the
# same set, so "solvable" always means "solvable for the bot".
BOT_ACTIONS = (
    NOOP,
    Action(left=True),
    Action(right=True),
    Action(jump=True),
    Action(right=True, jump=True),
    Action(shoot=True),
)
BOT_ACTION_NAMES = ("noop", "left", "right", "jump", "right+jump", "shoot", "left+jump")
# Phase 9 (models with the v3 observation): a 7th action "left+jump". Without it wide jumps to the left were
# impossible (jump straight up, then steer) - turning back, channels and mirrored levels need them. Index 0-5
# are unchanged, so old action lists replay the same through this tuple.
BOT_ACTIONS_V3 = BOT_ACTIONS + (Action(left=True, jump=True),)
ACTION_REPEAT = 4  # frames per bot decision (models up to phase 3, exam solutions)
DEFAULT_REPEAT = 2  # finer control for new models (phase 5+)
