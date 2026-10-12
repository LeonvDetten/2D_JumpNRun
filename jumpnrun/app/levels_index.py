"""Which levels the game offers (tabs), their titles and par times (the bot's time, for the stars)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from jumpnrun.app.progress import level_key
from jumpnrun.core.constants import PLAYER_SPEED, TILE
from jumpnrun.core.level import Level
from jumpnrun.editor.model import LEVELS_DIR, load_solution

# tab -> folders (in this order)
CATEGORIES = [
    ("Einstieg", ["phase1", "phase2", "showcase"]),
    ("Handgebaut", ["handmade8", "handmade9", "handmade10"]),
    ("Test-Serie", ["test_serie"]),
    ("Prüfung", ["exam", "exam2"]),
    ("Eigene", ["eigene"]),
]
RANDOM_TAB = "Zufall"

TIER_NAMES = (
    "Spaziergang", "Kleine Lücken", "Echte Lücken", "Gegner", "Plattformen", "Alles dabei", "Dicht gepackt",
    "Experte", "Klettern & Gruppen", "Wie die Prüfung", "Prüfungsmuster", "Lange Reise", "Sprungkatalog",
    "Kanäle & Gabeln",
)
SPECIAL_TITLES = {
    ("exam", "level"): "Das Prüfungslevel",
    ("exam", "level_entschaerft"): "Prüfung (entschärft)",
    ("exam2", "level"): "Prüfung 2",
    ("showcase", "luecken"): "Lücken",
    ("showcase", "gegner"): "Gegner",
}


@dataclass
class LevelEntry:
    title: str
    text: str
    folder: str = ""
    path: Optional[Path] = None
    par_frames: Optional[int] = None  # time of the bot's proven way (stars), or an estimate
    par_proven: bool = False  # True: par_frames is a real, stored bot solution
    tier: Optional[int] = None  # random levels
    seed: Optional[int] = None
    key: str = field(init=False)

    def __post_init__(self):
        self.key = level_key(self.text)

    def level(self) -> Level:
        return Level.from_text(self.text, name=self.title)

    @property
    def par_label(self) -> str:
        return "Bot-Weg" if self.par_proven else "Richtzeit"

    @property
    def subtitle(self) -> str:
        if self.tier is not None:
            return f"Zufall · Stufe {self.tier} · Seed {self.seed}"
        return f"levels/{self.folder}"


def pretty_title(folder: str, stem: str) -> str:
    if (folder, stem) in SPECIAL_TITLES:
        return SPECIAL_TITLES[(folder, stem)]
    words = [w for w in stem.replace("-", "_").split("_") if w]
    if words and words[0] in ("p1", "p2"):
        words = words[1:]
    words = [w.replace("ae", "ä").replace("oe", "ö").replace("ue", "ü") if w not in ("zuerst", "neue", "aue") else w
             for w in words]
    title = " ".join(w if w.isdigit() else w.capitalize() for w in words) or stem
    return title.replace(" 0", " ")


def par_frames(level: Level, solution: Optional[List[int]] = None) -> int:
    """Frames the bot needs: the stored proven way if there is one, else the way length at full speed."""

    if solution:
        return len(solution) * 2
    try:
        from jumpnrun.levelgen.distmap import DistanceMap

        dm = DistanceMap(level)
        if dm.start is not None:
            return int(dm.start * TILE / PLAYER_SPEED * 1.1)
    except Exception:  # pragma: no cover - only an estimate
        pass
    return max(30, (level.goal_x - level.spawn[0]) // PLAYER_SPEED)


def scan(only: Optional[str] = None) -> Dict[str, List[LevelEntry]]:
    """All tabs (or only the tab `only`) with their levels."""

    tabs: Dict[str, List[LevelEntry]] = {}
    for tab, folders in CATEGORIES:
        if only is not None and tab != only:
            continue
        entries = []
        for folder in folders:
            for path in sorted((LEVELS_DIR / folder).glob("*.txt")):
                try:
                    text = path.read_text(encoding="utf-8")
                    level = Level.from_text(text)
                except (OSError, ValueError, UnicodeDecodeError):
                    continue  # e.g. a half-built level without a chest
                entry = LevelEntry(pretty_title(folder, path.stem), text, folder, path)
                solution = load_solution(path)
                entry.par_frames = par_frames(level, solution)
                entry.par_proven = bool(solution)
                entries.append(entry)
        tabs[tab] = entries
    return tabs


def random_entry(tier: int, seed: int) -> LevelEntry:
    from jumpnrun.levelgen.generator import generate

    level = generate(tier, seed)
    entry = LevelEntry(f"{TIER_NAMES[tier]} #{seed}", level.to_text(), "", None, tier=tier, seed=seed)
    entry.par_frames = par_frames(level)
    return entry
