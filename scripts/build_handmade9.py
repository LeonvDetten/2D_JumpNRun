"""Phase 9: twelve hand-placed test levels (levels/handmade9), built by Claude at absolute coordinates.

    python3 scripts/build_handmade9.py            # write the levels, prove each with the solver, split them

Four kinds, three levels each - the situations phase 9 is about:
    forks and turning back   gabel_drei, kreuzung, spiegelgabel
    channels / serpentines   serpentine, kanal_links, turm
    Mario-inspired           roehrenwald, pyramiden, burg       (inspired only - no copied levels)
    long and mirrored        spiegelweg, langer_marsch, hin_und_zurueck
Like handmade8 they are not built from generator blocks. Each is proven solvable (the solver guided by the
distance map, 7 actions incl. left+jump); the solution is stored next to it. A fixed lottery (seed 20261003)
splits them into dev / test / sealed; the file hashes are fixed in tests/test_phase9.py.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "levels/handmade9"
ROWS = 13
GROUND = 12


class G:
    def __init__(self, cols: int):
        self.g = [[" "] * cols for _ in range(ROWS)]
        self.cols = cols

    def b(self, c, r):
        self.g[r][c] = "B"

    def floor(self, c0, c1, row=GROUND):  # solid from row down, columns c0..c1 inclusive
        for c in range(c0, c1 + 1):
            for r in range(row, ROWS):
                self.g[r][c] = "B"

    def plat(self, c0, w, row):  # floating platform
        for c in range(c0, c0 + w):
            self.g[row][c] = "B"

    def wall(self, c, r0, r1):
        for r in range(r0, r1 + 1):
            self.g[r][c] = "B"

    def stairs(self, c, base, n, d=1, width=1):
        """Solid staircase standing on row `base`: n steps, each one row higher, going in direction d."""
        for k in range(n):
            for w in range(width):
                col = c + d * (k * width + w)
                for r in range(base - 1 - k, base):
                    self.g[r][col] = "B"

    def roof(self, c0, c1, r0=0, r1=1):
        for c in range(c0, c1 + 1):
            for r in range(r0, r1 + 1):
                self.g[r][c] = "B"

    def e(self, c, r):
        self.g[r][c] = "E"

    def put(self, ch, c, r):
        self.g[r][c] = ch

    def mirror(self):
        for row in self.g:
            row.reverse()
        return self

    def text(self):  # rows keep their full width: empty columns behind the chest are a real void
        return "\n".join("".join(row) for row in self.g) + "\n"


# ------------------------------------------------------------------ forks and turning back
def gabel_drei():
    """Three storeys: the top road dead-ends (walk back to its start), the middle road is harmless, the floor is
    the way. Later a second fork where the floor ends in a wide pit and the upper road is right."""
    g = G(164)
    g.put("P", 2, 11)
    g.floor(0, 100)
    g.plat(16, 2, 11)
    g.plat(19, 2, 10)
    g.plat(22, 39, 9)  # middle road, cols 22-60
    g.plat(30, 2, 8)
    g.plat(33, 2, 7)
    g.plat(36, 40, 6)  # top road, no gaps, cols 36-75 ...
    g.wall(76, 3, 6)  # ... ends at a wall
    g.e(45, 11)
    g.e(52, 8)
    g.e(70, 11)
    g.e(86, 11)
    g.floor(104, 128)
    g.plat(117, 2, 11)
    g.plat(120, 2, 10)
    g.plat(123, 28, 9)  # the right way: upper road over the pit
    g.e(135, 8)
    g.floor(140, 163)  # the floor resumes behind a pit of 11
    g.e(150, 11)
    g.put("C", 158, 11)
    g.wall(160, 8, 11)
    return g


def kreuzung():
    """The right way switches: floor dead-ends (upper road right), then the upper road dead-ends (floor right,
    turn back), then two roads that both lead on - the upper one guarded by enemies."""
    g = G(176)
    g.put("P", 2, 11)
    g.floor(0, 55)
    g.plat(25, 2, 11)
    g.plat(28, 2, 10)
    g.plat(31, 2, 9)
    g.plat(34, 37, 8)  # road 1: cols 34-70, the floor below ends at 55
    g.e(44, 11)
    g.e(60, 7)
    g.floor(67, 150)
    g.plat(78, 2, 11)
    g.plat(81, 2, 10)
    g.plat(84, 2, 9)
    g.plat(87, 30, 8)  # road 2: cols 87-116, no gaps, wall at its end - the floor is right
    g.wall(116, 5, 7)
    g.e(100, 7)
    g.e(98, 11)
    g.e(112, 11)
    g.plat(124, 2, 11)
    g.plat(127, 3, 10)
    g.plat(132, 3, 10)
    g.plat(137, 3, 10)
    g.e(133, 9)
    g.e(144, 11)
    g.floor(153, 175)
    g.put("C", 170, 11)
    return g


def spiegelgabel():
    """Two forks, built left to right and then mirrored: the player starts on the right and walks left. The
    first upper road dead-ends at a wall (stay low or turn back), at the second the floor ends in a pit (go up)."""
    g = G(150)
    g.put("P", 3, 11)
    g.floor(0, 100)
    g.plat(20, 2, 11)
    g.plat(23, 2, 10)
    g.plat(26, 2, 9)
    g.plat(29, 26, 8)  # bait road, cols 29-54, no gaps
    g.wall(54, 5, 7)
    g.e(40, 11)
    g.plat(80, 2, 11)
    g.plat(83, 2, 10)
    g.plat(86, 2, 9)
    g.plat(89, 28, 8)  # the right way, cols 89-116, over the pit
    g.e(100, 7)
    g.floor(111, 149)  # pit 101-110 under the road
    g.e(125, 11)
    g.put("C", 146, 11)
    g.mirror()
    return g


# ------------------------------------------------------------------ channels / serpentines
def serpentine():
    """Right along the floor, stairs up, left, stairs up, right out at the top - with enemies in every layer, a
    pit in the floor and a hole in the 2nd layer that drops back to the start of the channel."""
    g = G(120)
    g.put("P", 2, 11)
    g.floor(0, 119)
    g.floor(14, 15)  # a gap in front of the channel
    for c in range(14, 16):
        for r in range(GROUND, ROWS):
            g.g[r][c] = " "
    g.wall(20, 0, 8)  # left wall, entrance rows 9-11
    g.plat(20, 46, 8)  # 2nd layer floor, cols 20-65
    for c in (38, 39):  # pit in the bottom corridor
        g.g[GROUND][c] = " "
    g.e(32, 11)
    g.e(55, 11)
    g.stairs(66, GROUND, 3)  # cols 66-68 up to row 9
    g.wall(69, 4, 12)
    g.e(48, 7)
    g.g[8][44] = " "  # hole: falls back to the bottom corridor
    g.plat(25, 44, 4)  # 3rd layer floor, cols 25-68
    g.stairs(23, 8, 3, d=-1)  # cols 23, 22, 21 up to row 5
    g.e(40, 3)
    g.e(58, 3)
    g.floor(70, 119, 5)  # out at the top right
    g.e(90, 4)
    g.put("C", 112, 4)
    g.wall(114, 1, 4)
    return g


def kanal_links():
    """Start bottom left; the bottom corridor (pits, platforms, enemies) leads right, stairs up, the open upper
    floor leads back left to the chest high above the start."""
    g = G(110)
    g.put("P", 3, 11)
    g.floor(0, 25)
    g.plat(28, 3, 11)
    g.plat(33, 3, 11)
    g.floor(38, 60)
    g.e(48, 11)
    g.floor(63, 99)
    g.e(80, 11)
    g.e(90, 11)
    g.plat(1, 95, 7)  # the upper floor, cols 1-95 (the corridor below is 4 rows high)
    g.stairs(96, GROUND, 4)  # cols 96-99 up to row 8
    g.wall(100, 0, 12)
    g.wall(0, 0, 12)
    g.e(60, 6)
    g.e(30, 6)
    g.plat(40, 4, 4)  # a block row above the upper floor (jump under or over)
    g.put("C", 4, 6)
    return g


def turm():
    """Start bottom right. Bottom to the left, stairs up, right, stairs up, left to the chest top left.
    No enemies: a pure way-finding level (with enemies in the closed corridors the solver found no proof)."""
    g = G(70)
    g.put("P", 64, 11)
    g.floor(0, 69)
    g.wall(69, 0, 12)
    g.wall(0, 0, 12)
    g.plat(4, 65, 8)  # 2nd floor, cols 4-68 (opening on the left)
    g.stairs(3, GROUND, 3, d=-1)  # cols 3, 2, 1 up to row 9
    g.plat(1, 62, 4)  # 3rd floor, cols 1-62 (opening above the stairs) ...
    g.plat(66, 3, 4)  # ... and a ledge right of it: step up, then jump back left over the opening
    g.stairs(63, 8, 3)  # cols 63-65 up to row 5
    g.g[8][36] = " "  # a hole in the 2nd floor
    g.put("C", 3, 3)
    return g


# ------------------------------------------------------------------ Mario-inspired
def roehrenwald():
    """Pipes of different heights with steps, enemies trapped between them, pits between some pipes."""
    g = G(150)
    g.put("P", 2, 11)
    g.floor(0, 149)
    x = 10
    for h, pit, enemy in ((1, 0, 0), (2, 0, 1), (1, 2, 0), (2, 0, 1), (1, 3, 1), (2, 2, 0), (1, 0, 1), (2, 3, 1)):
        if h == 2:
            g.floor(x, x, GROUND - 1)
            x += 1
        g.floor(x, x + 1, GROUND - h)
        x += 2
        if pit:
            for c in range(x, x + pit):
                g.g[GROUND][c] = " "
            x += pit
        g.floor(x, x + 4)
        if enemy:
            g.e(x + 2, 11)
        x += 5 + (x % 3)
    g.plat(x + 3, 3, 8)
    g.e(x + 4, 7)
    g.put("C", 145, 11)
    return g


def pyramiden():
    """Block staircases up and down with pits between them; a brick bridge over a long pit with enemies."""
    g = G(170)
    g.put("P", 2, 11)
    g.floor(0, 20)
    g.stairs(14, GROUND, 4)  # 14-17 up to row 8
    g.floor(18, 18, 8)
    g.floor(21, 21, 8)  # pit of 2 at the top
    g.stairs(25, GROUND, 4, d=-1)  # 25, 24, 23, 22 going down to the right
    g.floor(22, 45)
    g.e(35, 11)
    g.stairs(40, GROUND, 3)
    g.floor(43, 43, 9)
    g.floor(47, 48, 10)  # pit of 3, lower landing
    g.floor(49, 60, 11)
    g.e(55, 10)
    g.plat(63, 1, 10)
    g.plat(65, 1, 9)
    g.plat(67, 1, 8)
    g.plat(69, 14, 8)  # brick bridge over a long pit
    g.e(74, 7)
    g.e(79, 7)
    g.floor(86, 110)
    g.stairs(98, GROUND, 4)
    g.floor(102, 103, 8)
    g.stairs(107, GROUND, 3, d=-1)
    g.e(115, 11)
    g.floor(111, 169)
    g.stairs(150, GROUND, 4)
    g.floor(154, 158, 8)
    g.put("C", 157, 7)
    g.wall(159, 4, 7)
    return g


def burg():
    """A castle: low brick ceilings over pits, a corridor with an enemy group, a staircase pyramid to the chest."""
    g = G(140)
    g.put("P", 2, 11)
    g.floor(0, 30)
    g.roof(10, 30, 0, 8)  # ceiling: only 3 rows below it
    g.floor(33, 60)
    g.roof(33, 60, 0, 8)
    g.e(40, 11)
    g.e(42, 11)
    g.e(52, 11)
    g.floor(63, 80, 11)
    g.roof(63, 80, 0, 7)
    g.e(70, 10)
    g.floor(83, 139)
    g.plat(86, 2, 9)
    g.plat(91, 2, 9)
    g.e(96, 11)
    g.e(98, 11)
    g.e(100, 11)
    g.stairs(110, GROUND, 4)
    g.floor(114, 120, 8)
    g.stairs(124, GROUND, 4, d=-1)
    g.put("C", 132, 11)
    g.wall(134, 6, 11)
    return g


# ------------------------------------------------------------------ long and mirrored
def spiegelweg():
    """A whole course from right to left: gaps, platforms, enemies walking towards the player, a stepping-stone
    chain - the chest at the far left."""
    g = G(170)
    g.put("P", 3, 11)
    g.floor(0, 20)
    g.e(15, 11)
    g.floor(23, 40)
    g.stairs(30, GROUND, 2)
    g.floor(32, 40, 10)
    g.plat(43, 3, 10)
    g.plat(48, 2, 9)
    g.plat(53, 3, 9)
    g.floor(59, 80)
    g.e(70, 11)
    g.e(74, 11)
    for c, r in ((84, 11), (88, 11), (92, 10), (96, 10), (100, 11)):  # stepping stones
        g.plat(c, 1, r)
    g.floor(104, 130)
    g.roof(110, 125, 0, 8)
    g.e(118, 11)
    g.floor(133, 169)
    g.e(150, 11)
    g.put("C", 165, 11)
    g.mirror()
    return g


def langer_marsch():
    """A long level (about 3x the usual length) mixing everything: forks, stairs, pits, enemies."""
    g = G(420)
    g.put("P", 2, 11)
    x = 0
    rng = random.Random(9)
    g.floor(0, 12)
    x = 13
    while x < 395:
        kind = rng.choice(("gap", "plats", "stairs", "enemies", "fork"))
        if kind == "gap":
            w = rng.randint(1, 3)
            g.floor(x + w, x + w + 8)
            x += w + 9
        elif kind == "plats":
            g.plat(x + 2, 2, 11)
            g.plat(x + 6, 3, 10)
            g.floor(x + 11, x + 18)
            x += 19
        elif kind == "stairs":
            g.floor(x, x + 12)
            g.stairs(x + 3, GROUND, 3)
            g.floor(x + 6, x + 8, 9)
            g.stairs(x + 11, GROUND, 3, d=-1)
            x += 13
        elif kind == "enemies":
            g.floor(x, x + 14)
            for c in rng.sample(range(x + 3, x + 13), 2):
                g.e(c, 11)
            x += 15
        else:
            g.floor(x, x + 30)
            g.plat(x + 4, 2, 11)
            g.plat(x + 7, 2, 10)
            g.plat(x + 10, 2, 9)
            g.plat(x + 13, 16, 8)
            g.wall(x + 28, 5, 7)
            x += 31
    g.floor(x, x + 10)
    g.put("C", x + 8, 11)
    return g


def hin_und_zurueck():
    """Along a lower road to the right end, up a staircase, and back left on an upper road to the chest, which
    stands right above the start (the lower road dead-ends under a wall)."""
    g = G(130)
    g.put("P", 3, 11)
    g.floor(0, 30)
    g.floor(33, 60)
    g.e(45, 11)
    g.plat(63, 3, 11)
    g.plat(68, 3, 11)
    g.floor(73, 115)
    g.e(85, 11)
    g.e(95, 11)
    g.wall(116, 0, 12)
    g.stairs(111, GROUND, 3)  # cols 111-113 up to row 9, then back left over them onto the bridge step
    g.plat(6, 102, 7)  # the upper road, cols 6-107
    g.plat(108, 3, 8)  # bridge step from the stairs
    g.e(40, 6)
    g.e(70, 6)
    g.wall(5, 2, 7)
    g.put("C", 8, 6)
    return g


LEVELS = [gabel_drei, kreuzung, spiegelgabel, serpentine, kanal_links, turm, roehrenwald, pyramiden, burg,
          spiegelweg, langer_marsch, hin_und_zurueck]


def prove(name):
    from jumpnrun.core.level import Level
    from jumpnrun.levelgen.solver import solve_auto

    level = Level.from_file(OUT / f"{name}.txt")
    r = solve_auto(level, 300_000, action_repeat=2, weight=1.2, path=True)
    if not r.solved:
        r = solve_auto(level, 600_000, action_repeat=2, weight=1.6, path=True)
    if r.solved:
        (OUT / f"{name}.loesung.json").write_text(json.dumps({"action_repeat": 2, "actions": list(r.actions)}))
    return name, bool(r.solved)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    names = []
    for fn in LEVELS:
        (OUT / f"{fn.__name__}.txt").write_text(fn().text())
        names.append(fn.__name__)
    only = sys.argv[1:]
    with Pool(4) as p:
        results = dict(p.map(prove, [n for n in names if not only or n in only]))
    print(results)
    if not all(results.values()) or only:
        print("UNSOLVED:", [n for n, ok in results.items() if not ok])
        return
    order = sorted(names)
    random.Random(20261003).shuffle(order)
    split = {"dev": sorted(order[:4]), "test": sorted(order[4:8]), "sealed": sorted(order[8:])}
    split["sha256"] = {n: hashlib.sha256((OUT / f"{n}.txt").read_bytes()).hexdigest() for n in names}
    (OUT / "split.json").write_text(json.dumps(split, indent=1))
    print({k: v for k, v in split.items() if k != "sha256"})


if __name__ == "__main__":
    main()
