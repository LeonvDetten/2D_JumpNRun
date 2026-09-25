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
BOT_ACTION_NAMES = ("noop", "left", "right", "jump", "right+jump", "shoot")
ACTION_REPEAT = 4  # frames per bot decision
