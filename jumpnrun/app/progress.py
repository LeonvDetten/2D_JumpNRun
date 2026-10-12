"""Save game: settings, best times, stars and the inputs of the best run (for the ghost).

Stored in ~/.space_pirate/save.json (override with the environment variable SPACE_PIRATE_HOME), never in the repo.
A level is identified by a hash of its text, so an edited level starts a fresh record.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import List, Optional

from jumpnrun.core.actions import Action
from jumpnrun.core.constants import FPS

DEFAULT_SETTINGS = {
    "fullscreen": False,
    "music": 0.5,
    "sfx": 0.8,
    "ghost": True,
    "head_start": 2,  # seconds the player starts before the bot
}
HEAD_STARTS = (0, 2, 5, 10)
STAR_LIMITS = (1.15, 1.5)  # <= par * 1.15: three stars, <= par * 1.5: two stars, finished: one star


def save_dir() -> Path:
    return Path(os.environ.get("SPACE_PIRATE_HOME") or Path.home() / ".space_pirate")


def level_key(text: str) -> str:
    rows = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while rows and not rows[-1]:
        rows.pop()
    return hashlib.sha1("\n".join(rows).encode("utf-8")).hexdigest()[:16]


def stars_for(frames: int, par_frames: Optional[int]) -> int:
    if not par_frames:
        return 1
    if frames <= par_frames * STAR_LIMITS[0]:
        return 3
    if frames <= par_frames * STAR_LIMITS[1]:
        return 2
    return 1


def format_time(frames: Optional[int]) -> str:
    if frames is None:
        return "–:––.––"
    seconds = frames / FPS
    return f"{int(seconds // 60)}:{seconds % 60:05.2f}"


# --------------------------------------------------------------- inputs (one hex digit per frame)
def encode_action(action: Action) -> int:
    return int(action.left) | int(action.right) << 1 | int(action.jump) << 2 | int(action.shoot) << 3


def decode_action(code: int) -> Action:
    return Action(bool(code & 1), bool(code & 2), bool(code & 4), bool(code & 8))


def encode_inputs(codes: List[int]) -> str:
    return "".join("0123456789abcdef"[c] for c in codes)


def decode_inputs(text: str) -> List[int]:
    return [int(ch, 16) for ch in text]


class Progress:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else save_dir() / "save.json"
        self.settings = dict(DEFAULT_SETTINGS)
        self.levels = {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.settings.update({k: v for k, v in data.get("settings", {}).items() if k in DEFAULT_SETTINGS})
            self.levels = data.get("levels", {})
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"version": 1, "settings": self.settings, "levels": self.levels}), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass  # a read-only home must not stop the game

    def get(self, key: str) -> dict:
        return self.levels.get(key, {})

    def best_frames(self, key: str) -> Optional[int]:
        return self.get(key).get("best")

    def stars(self, key: str) -> int:
        return self.get(key).get("stars", 0)

    def ghost(self, key: str) -> Optional[List[int]]:
        inputs = self.get(key).get("inputs")
        return decode_inputs(inputs) if inputs else None

    def record_win(self, key: str, frames: int, inputs: List[int], par_frames: Optional[int]) -> dict:
        """A finished single-player run. Returns {'best': new best?, 'stars': stars of this run, 'old_best': ...}."""

        entry = self.levels.setdefault(key, {})
        old = entry.get("best")
        stars = stars_for(frames, par_frames)
        new_best = old is None or frames < old
        if new_best:
            entry["best"] = frames
            entry["inputs"] = encode_inputs(inputs)
        entry["stars"] = max(entry.get("stars", 0), stars)
        entry["wins"] = entry.get("wins", 0) + 1
        self.save()
        return {"best": new_best, "stars": stars, "old_best": old}

    def record_race(self, key: str, won: bool, frames: int) -> dict:
        entry = self.levels.setdefault(key, {})
        entry["races"] = entry.get("races", 0) + 1
        if won:
            entry["race_wins"] = entry.get("race_wins", 0) + 1
            if entry.get("race_best") is None or frames < entry["race_best"]:
                entry["race_best"] = frames
        self.save()
        return {"wins": entry.get("race_wins", 0), "races": entry["races"]}
