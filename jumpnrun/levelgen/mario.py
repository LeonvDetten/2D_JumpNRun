"""Phase 12 extension: training levels from real platformer levels (VGLC - The Video Game Level Corpus,
https://github.com/TheVGLC/TheVGLC, MIT; Super Mario Bros., Super Mario Bros. 2 (Japan), Super Mario Land).

    python3 -m jumpnrun.levelgen.mario build      # download (git) + convert -> runs/mario/{pool,holdout}.jsonl

The level layouts belong to their publisher, so no converted level is committed - only this converter.

Conversion:
1. Tiles -> ours: ground, bricks, question blocks, pipes, cannons -> "B"; enemies -> "E"; the rest empty.
   The bottom 13 rows are kept (our levels are 13 high).
2. Segments of 60-150 columns are cut out; player spawn on the left, chest on the right.
3. Repair for our physics (the player jumps only a little more than one tile high, Mario four): while the chest
   cannot be reached from the spawn (tile graph of jumpnrun.levelgen.distmap), the obstacle right of the
   furthest reachable place is cut down to a one-tile step (stairs keep their shape, one step per column)
   or a pit is narrowed by one floor tile. Segments needing too many repairs are dropped.
4. Whole levels (every 5th file) are held out: never trained, only measured ("mario" probes).
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from jumpnrun.core.constants import ROWS
from jumpnrun.core.level import Level

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "runs/vglc_src/repo"
OUT = ROOT / "runs/mario"
GAMES = {"smb": ("Super Mario Bros", "Processed"), "smb2j": ("Super Mario Bros 2 (Japan)", "Processed"),
         "sml": ("Super Mario Land", "Processed")}
SOLID = set("XS?Q<>[]Bb#%|")  # VGLC symbols for solid tiles (ground, bricks, blocks, pipes, cannons)
MAX_REPAIRS = 120


def _rows(path: Path) -> List[str]:
    lines = [l.rstrip("\n") for l in path.read_text().splitlines() if l.strip()]
    w = max(len(l) for l in lines)
    lines = [l.ljust(w, "-") for l in lines]
    lines = lines[-ROWS:]
    while len(lines) < ROWS:
        lines.insert(0, "-" * w)
    out = []
    for l in lines:
        out.append("".join("B" if ch in SOLID else "E" if ch in "Eg" else " " for ch in l))
    return out


def source_levels() -> List[Tuple[str, List[str]]]:
    levels = []
    for tag, (game, sub) in GAMES.items():
        d = SRC / game / sub
        for p in sorted(d.glob("*.txt")):
            levels.append((f"{tag}_{p.stem.replace('.png', '')}", _rows(p)))
    return levels


def download() -> None:
    if SRC.exists():
        return
    SRC.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse",
                    "https://github.com/TheVGLC/TheVGLC.git", str(SRC)], check=True)
    subprocess.run(["git", "-C", str(SRC), "sparse-checkout", "set", *[g for g, _ in GAMES.values()]], check=True)


# ------------------------------------------------------------------------------------------------ repair
def _grid(lines: List[str]) -> List[List[str]]:
    return [list(l) for l in lines]


def _text(grid: List[List[str]]) -> List[str]:
    return ["".join(r).rstrip() for r in grid]


def _top(grid, col: int) -> Optional[int]:
    """Row of the lowest solid tile in `col` with free space above it (the floor), None for a pit."""

    for r in range(ROWS - 1, 0, -1):  # the lowest floor (the ground, not a floating block)
        if grid[r][col] == "B" and grid[r - 1][col] != "B":
            return r
    return None


def _reach(level: Level):
    from jumpnrun.levelgen.distmap import DistanceMap

    dm = DistanceMap(level)
    start = None
    x, y = level.spawn
    start = dm.at_xy(x, y, 40, 60) if dm.reachable else None
    if dm.reachable and start is None:
        start = dm.below(x, y, 40, 60)
    # forward search from the spawn cell over the move graph
    from jumpnrun.core.constants import TILE

    sc = (x // TILE, min(ROWS - 2, (y + 59) // TILE))
    if sc not in dm.stand:
        r = sc[1]
        while r < ROWS - 1 and (sc[0], r) not in dm.stand:
            r += 1
        sc = (sc[0], r)
    seen = {sc} if sc in dm.stand else set()
    todo = list(seen)
    while todo:
        u = todo.pop()
        for v, _ in dm.edges.get(u, []):
            if v not in seen:
                seen.add(v)
                todo.append(v)
    goal = start is not None  # at_xy / below give the remaining way (None = no way to the chest)
    return goal, seen


def place(grid, spawn_col: int, chest_col: int) -> bool:
    """Spawn on the floor near the left, chest on the floor near the right (floor added if there is none)."""

    for c in (spawn_col, chest_col):
        if _top(grid, c) is None:
            grid[ROWS - 1][c] = "B"
            grid[ROWS - 2][c] = "B"
    rs, rc = _top(grid, spawn_col), _top(grid, chest_col)
    for r in range(rs):
        if grid[r][spawn_col] == "E":
            grid[r][spawn_col] = " "
    grid[rs - 1][spawn_col] = "P"
    grid[rc - 1][chest_col] = "C"
    return True


def repair(lines: List[str], name: str) -> Optional[Tuple[Level, int]]:
    grid = _grid(lines)
    w = len(grid[0])
    place(grid, 1, w - 2)
    fixes = 0
    while True:
        level = Level(_text(grid), name=name)
        ok, seen = _reach(level)
        if ok:
            level.needs_path = True
            return level, fixes
        if fixes >= MAX_REPAIRS or not seen:
            return None
        c, r = max(seen, key=lambda u: (u[0], -u[1]))
        n = c + 1
        if n >= w:
            return None
        fixes += 1
        if grid[r][n] == "B" or grid[r - 1][n] == "B":  # wall: cut it down to a one-tile step
            rr = r - 1
            while rr >= 0 and grid[rr][n] == "B":  # the stack above the step
                grid[rr][n] = " "
                rr -= 1
            for rr in (r - 1, r - 2):  # headroom for the step / jump
                if rr >= 0 and grid[rr][c] == "B":
                    grid[rr][c] = " "
        else:  # pit or drop that cannot be crossed: extend the floor by one tile
            grid[r + 1][n] = "B"


def segments(lines: List[str], rng: random.Random, count: int) -> List[List[str]]:
    w = len(lines[0])
    out = []
    for _ in range(count):
        width = rng.randint(60, 150)
        if width >= w - 4:
            a = 0
            width = w
        else:
            a = rng.randint(0, w - width)
        seg = [l[a:a + width] for l in lines]
        out.append(seg)
    return out


def build(per_level: int = 25, seed: int = 0) -> dict:
    download()
    rng = random.Random(seed)
    OUT.mkdir(parents=True, exist_ok=True)
    src = source_levels()
    stats = {"quellen": len(src), "pool": 0, "holdout": 0, "verworfen": 0, "reparaturen": 0}
    with (OUT / "pool.jsonl").open("w") as pool, (OUT / "holdout.jsonl").open("w") as hold:
        for i, (name, lines) in enumerate(src):
            held = i % 5 == 4
            segs = segments(lines, random.Random(f"{name}:{seed}"), 4 if held else per_level)
            for k, seg in enumerate(segs):
                res = repair(seg, f"mario_{name}_{k}")
                if res is None:
                    stats["verworfen"] += 1
                    continue
                level, fixes = res
                stats["reparaturen"] += fixes
                row = {"name": level.name, "quelle": name, "text": level.to_text(), "reparaturen": fixes}
                (hold if held else pool).write(json.dumps(row) + "\n")
                stats["holdout" if held else "pool"] += 1
    stats["holdout_level"] = [n for i, (n, _) in enumerate(src) if i % 5 == 4]
    (OUT / "stats.json").write_text(json.dumps(stats, indent=1))
    return stats


class MarioSource:
    """MixSource "mario": repaired VGLC segments (never the held-out levels), mirrored with `mirror_prob`."""

    MARIO_TIER = -8

    def __init__(self, path: Path = OUT / "pool.jsonl", mirror_prob: float = 0.3):
        self.items = [json.loads(l) for l in path.read_text().splitlines()]
        self.mirror_prob = mirror_prob

    def __call__(self, rng: random.Random):
        from jumpnrun.levelgen.skills import mirror_level

        item = rng.choice(self.items)
        level = Level(item["text"].splitlines(), name=item["name"])
        level.needs_path = True
        aug = []
        if rng.random() < self.mirror_prob:
            level = mirror_level(level)
            aug = ["mirror"]
        level.source = "mario"
        level.augmentations = aug
        level.family = "mario"
        return level, self.MARIO_TIER

    def feedback(self, *args, **kwargs) -> None:
        pass


def holdout_levels(mirror: bool = True) -> List[Level]:
    from jumpnrun.levelgen.skills import mirror_level

    items = [json.loads(l) for l in (OUT / "holdout.jsonl").read_text().splitlines()]
    out = []
    for it in items:
        lv = Level(it["text"].splitlines(), name=it["name"])
        lv.needs_path = True
        out.append(lv)
        if mirror:
            out.append(mirror_level(lv))
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["build"]:
        print(json.dumps(build(), indent=1))
