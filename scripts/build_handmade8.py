"""Phase 8: twelve hand-placed test levels (levels/handmade8), built by Claude at absolute coordinates.

    python3 scripts/build_handmade8.py            # write the levels, prove each with the solver, split them

They are deliberately NOT built from generator blocks: features sit at hand-picked places, combine
situations (enemies on stairs, ceilings over jumps, bait roads, high stones, void behind the chest, start in
the air) and vary rhythm. Each level is proven solvable (solution stored next to it). A fixed lottery
(seed 20261002) splits them into dev / test / sealed; the file hashes are fixed in tests/test_phase8.py.
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
OUT = ROOT / "levels/handmade8"
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

    def roof(self, c0, c1, r0=0, r1=1):
        for c in range(c0, c1 + 1):
            for r in range(r0, r1 + 1):
                self.g[r][c] = "B"

    def e(self, c, r):
        self.g[r][c] = "E"

    def put(self, ch, c, r):
        self.g[r][c] = ch

    def text(self):  # rows keep their full width: empty columns behind the chest are a real void
        return "\n".join("".join(row) for row in self.g) + "\n"


def hoehlendach():
    """A cave: solid roof, short jumps under it, a one-row tunnel with an enemy, void behind the chest."""
    g = G(170)
    g.roof(0, 169, 0, 3)
    g.put("P", 1, 11)
    g.floor(0, 20)
    g.e(14, 11)
    g.floor(23, 40)
    g.plat(30, 3, 9)
    g.e(36, 11)
    g.floor(43, 46, 11)
    g.floor(49, 75)
    g.roof(56, 70, 4, 10)  # low tunnel: one row high above the floor
    g.e(66, 11)
    g.plat(79, 2, 11)
    g.plat(84, 2, 10)
    g.plat(89, 2, 11)
    g.floor(93, 120)
    g.e(100, 11)
    g.e(108, 11)
    g.roof(104, 112, 4, 8)
    g.floor(123, 130, 11)
    g.floor(133, 140, 10)
    g.e(137, 9)
    g.floor(143, 150)
    g.put("C", 150, 11)
    return g


def koeder():
    """A tempting stair to an upper road that ends at a wall above a pit; the floor is the way."""
    g = G(190)
    g.put("P", 1, 11)
    g.floor(0, 30)
    g.plat(10, 2, 11)
    g.plat(14, 2, 10)
    g.plat(18, 2, 9)
    g.plat(22, 14, 8)
    g.plat(39, 10, 7)
    g.wall(48, 4, 6)
    g.floor(33, 44)
    g.floor(47, 70)  # pit 45-46 under the road's end
    g.e(55, 11)
    g.e(62, 11)
    g.floor(73, 90)
    g.plat(78, 3, 9)
    g.e(84, 11)
    # a second fork: now the upper way is right, the floor ends in a long pit
    g.plat(92, 2, 11)
    g.plat(96, 2, 10)
    g.plat(100, 12, 9)
    g.floor(93, 112)
    g.plat(115, 10, 8)
    g.e(120, 7)
    g.plat(128, 3, 8)
    g.plat(134, 3, 9)
    g.floor(139, 160, 10)
    g.e(150, 9)
    g.floor(163, 170)
    g.put("C", 170, 11)
    return g


def abgrund():
    """Start in the air, long falls onto small ledges, the chest on the very edge of a void."""
    g = G(260)
    g.put("P", 2, 5)
    g.plat(1, 4, 7)
    g.plat(8, 3, 9)
    g.floor(13, 30)
    g.e(22, 11)
    g.plat(33, 2, 11)
    g.plat(38, 2, 10)
    g.plat(42, 2, 9)
    g.plat(47, 3, 9)
    g.floor(53, 54)  # a narrow pillar after a long fall
    g.floor(58, 80, 11)
    g.e(66, 10)
    g.e(74, 10)
    g.plat(83, 2, 10)
    g.plat(88, 2, 9)
    g.plat(93, 2, 8)
    g.plat(98, 2, 8)
    g.floor(104, 108)
    g.floor(111, 125)
    g.e(118, 11)
    g.put("C", 125, 11)  # nothing behind the chest: 134 empty columns
    return g


def gegnertreppe():
    """Solid staircases with enemies coming down; one has a ceiling over the top."""
    g = G(200)
    g.put("P", 1, 11)
    g.floor(0, 15)
    for i, c in enumerate(range(16, 34, 3)):
        g.floor(c, c + 2, 11 - i)
    g.floor(34, 44, 5)
    g.e(38, 4)
    g.e(42, 4)
    g.e(30, 5)
    g.floor(45, 47, 6)
    g.floor(48, 50, 7)
    g.floor(51, 53, 8)
    g.floor(54, 70, 9)
    g.e(60, 8)
    g.floor(73, 90)
    g.e(80, 11)
    g.e(84, 11)
    for i, c in enumerate(range(91, 106, 3)):
        g.floor(c, c + 2, 11 - i)
    g.floor(106, 120, 6)
    g.roof(106, 120, 0, 3)
    g.e(112, 5)
    g.e(117, 5)
    g.floor(123, 126, 7)
    g.floor(129, 150, 9)
    g.e(140, 8)
    g.floor(153, 160)
    g.put("C", 160, 11)
    return g


def hochsteine():
    """Stepping stones in the top rows (row 2-3), above a deep void."""
    g = G(200)
    g.put("P", 1, 11)
    g.floor(0, 12)
    g.plat(14, 2, 11)
    g.plat(18, 2, 10)
    g.plat(22, 2, 9)
    g.plat(26, 2, 8)
    g.plat(30, 2, 7)
    g.plat(34, 2, 6)
    g.plat(38, 2, 5)
    g.plat(42, 2, 4)
    g.plat(46, 2, 3)
    g.b(51, 3)
    g.b(55, 2)
    g.b(59, 2)
    g.b(63, 3)
    g.b(67, 3)
    g.b(71, 2)
    g.plat(75, 4, 2)
    g.e(77, 1)
    g.b(82, 3)
    g.b(86, 4)
    g.b(90, 5)
    g.b(94, 5)
    g.plat(98, 3, 6)
    g.floor(104, 130, 11)
    g.e(115, 10)
    g.e(122, 10)
    g.floor(133, 140)
    g.put("C", 140, 11)
    return g


def regenstart():
    """Start in the air, enemies drop from the sky onto floating stairs."""
    g = G(180)
    g.put("P", 2, 6)
    g.floor(0, 10)
    for c in (4, 6, 8):
        g.e(c, 0)
    g.plat(13, 3, 11)
    g.plat(18, 3, 10)
    g.plat(23, 3, 9)
    g.plat(28, 3, 8)
    for c in (14, 19, 24, 29):
        g.e(c, 0)
    g.plat(33, 12, 7)
    g.e(38, 0)
    g.e(42, 0)
    g.floor(48, 70, 10)
    g.e(55, 9)
    g.e(60, 0)
    g.e(64, 0)
    g.floor(73, 75, 11)
    g.floor(78, 100)
    g.e(85, 0)
    g.e(90, 0)
    g.e(95, 11)
    g.floor(103, 110)
    g.put("C", 110, 11)
    return g


def turm():
    """A long climb from the floor to row 2, a road in the top rows, a careful way down on small ledges."""
    g = G(170)
    g.put("P", 1, 11)
    g.floor(0, 14)
    for i in range(10):  # rows 11 .. 2, one row per hop
        g.plat(15 + 4 * i, 2, 11 - i)
    g.e(43, 4)
    g.plat(55, 14, 2)
    g.e(62, 1)
    g.b(72, 3)
    g.b(76, 4)
    g.plat(80, 2, 5)
    g.plat(85, 2, 7)
    g.plat(90, 2, 9)
    g.floor(95, 115, 11)
    g.e(105, 10)
    g.floor(118, 121)
    g.floor(124, 135)
    g.put("C", 135, 11)
    return g


def zickzack():
    """Platforms that alternate up and down with enemies patrolling on them."""
    g = G(200)
    g.put("P", 1, 11)
    g.floor(0, 8)
    rows = [11, 10, 11, 10, 9, 10, 9, 8, 9, 10]
    c = 11
    for i, r in enumerate(rows):
        w = 4 if i % 3 else 5
        g.plat(c, w, r)
        if i in (1, 3, 5, 8):
            g.e(c + w - 1, r - 1)
        c += w + 2
    g.floor(c + 1, c + 20)
    g.e(c + 10, 11)
    g.e(c + 14, 11)
    g.floor(c + 23, c + 30)
    g.put("C", c + 30, 11)
    return g


def lange_tour():
    """A long level that mixes everything in a calm rhythm."""
    g = G(330)
    g.put("P", 1, 11)
    g.floor(0, 25)
    g.e(18, 11)
    g.floor(28, 40, 11)
    g.floor(43, 60, 10)
    g.e(52, 9)
    g.plat(63, 2, 9)
    g.plat(68, 2, 9)
    g.plat(73, 2, 10)
    g.floor(78, 110)
    g.roof(84, 100, 0, 9)  # a tunnel two rows high
    g.e(92, 11)
    g.plat(113, 3, 11)
    g.plat(118, 3, 10)
    g.plat(123, 3, 9)
    g.plat(128, 20, 8)
    g.floor(126, 140)
    g.e(135, 11)
    g.wall(147, 5, 7)  # the upper road ends at a wall; drop to the floor before it
    g.floor(143, 170)
    g.e(160, 11)
    g.b(174, 11)
    g.b(178, 10)
    g.b(182, 10)
    g.b(186, 11)
    g.floor(190, 220)
    for i, c in enumerate(range(200, 212, 3)):
        g.floor(c, c + 2, 11 - i)
    g.floor(212, 220, 7)
    g.e(216, 6)
    g.floor(223, 230, 9)
    g.floor(233, 260)
    g.e(245, 11)
    g.e(250, 0)
    g.floor(263, 270)
    g.put("C", 270, 11)
    return g


def stollen():
    """Low tunnels with enemies that must be shot, gaps under a low roof."""
    g = G(170)
    g.put("P", 1, 11)
    g.floor(0, 30)
    g.roof(8, 30, 0, 10)
    g.e(20, 11)
    g.e(27, 11)
    g.floor(33, 50)
    g.roof(33, 50, 0, 8)
    g.e(45, 11)
    g.floor(53, 54)
    g.floor(57, 80)
    g.roof(57, 80, 0, 9)
    g.e(65, 11)
    g.e(70, 11)
    g.e(76, 11)
    g.plat(83, 2, 11)
    g.floor(88, 110)
    g.roof(95, 110, 0, 10)
    g.e(105, 11)
    g.floor(113, 120)
    g.put("C", 120, 11)
    return g


def pruefungsstil():
    """In the style of a long exam: rain at the start, fork, stones, diagonals, chest on the edge."""
    g = G(330)
    g.put("P", 2, 9)
    g.floor(0, 12)
    for c in range(3, 25, 3):
        g.e(c, 0)
    for i, r in enumerate([11, 10, 9, 8, 7, 6]):
        g.plat(14 + 4 * i, 3, r)
    g.plat(38, 18, 5)
    g.e(45, 4)
    g.floor(14, 70)
    g.e(30, 11)
    g.e(40, 11)
    g.wall(70, 6, 11)  # the floor ends at a wall; the upper road is right
    g.plat(59, 3, 5)
    g.b(65, 5)
    g.b(69, 4)
    g.b(73, 4)
    g.b(77, 5)
    g.b(81, 5)
    g.b(85, 4)
    g.plat(89, 3, 3)
    g.b(95, 4)
    g.b(99, 5)
    g.b(103, 6)
    g.b(107, 7)
    g.b(111, 8)
    g.plat(115, 4, 9)
    g.e(117, 8)
    g.floor(122, 150, 11)
    g.e(130, 10)
    g.e(134, 10)
    g.e(140, 0)
    g.plat(153, 2, 10)
    g.plat(157, 2, 9)
    g.plat(161, 2, 8)
    g.plat(165, 2, 7)
    g.plat(170, 2, 9)
    g.plat(175, 2, 11)
    g.floor(180, 205)
    g.put("C", 205, 11)
    return g


def doppelgabel():
    """Two forks in a row: first the lower way is right, then the upper one."""
    g = G(220)
    g.put("P", 1, 11)
    g.floor(0, 60)
    g.e(30, 11)
    g.plat(8, 2, 11)
    g.plat(12, 2, 10)
    g.plat(16, 2, 9)
    g.plat(20, 25, 8)
    g.wall(44, 5, 7)
    g.floor(63, 64, 11)
    g.floor(67, 100)
    g.e(80, 11)
    g.e(88, 11)
    g.plat(70, 2, 11)
    g.plat(74, 2, 10)
    g.plat(78, 2, 9)
    g.plat(82, 28, 8)
    g.e(95, 7)
    g.wall(100, 9, 11)  # floor dead end: wall too high to climb from the floor
    g.plat(113, 2, 8)
    g.plat(118, 2, 9)
    g.floor(123, 150, 10)
    g.e(135, 9)
    g.floor(153, 160)
    g.put("C", 160, 11)
    return g


LEVELS = [hoehlendach, koeder, abgrund, gegnertreppe, hochsteine, regenstart, turm, zickzack, lange_tour,
          stollen, pruefungsstil, doppelgabel]


def prove(name):
    from jumpnrun.core.level import Level
    from jumpnrun.levelgen.solver import solve_auto

    level = Level.from_file(OUT / f"{name}.txt")
    r = solve_auto(level, 150_000, action_repeat=2, weight=1.2)
    if not r.solved:  # long hand-made levels have no waypoints: one bigger, greedier search
        from jumpnrun.levelgen.solver import solve

        r = solve(level, 400_000, action_repeat=2, weight=1.5)
    if r.solved:
        (OUT / f"{name}.loesung.json").write_text(json.dumps({"action_repeat": 2, "actions": list(r.actions)}))
    return name, bool(r.solved)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    names = []
    for fn in LEVELS:
        (OUT / f"{fn.__name__}.txt").write_text(fn().text())
        names.append(fn.__name__)
    with Pool(4) as p:
        results = dict(p.map(prove, names))
    print(results)
    if not all(results.values()):
        print("UNSOLVED:", [n for n, ok in results.items() if not ok])
        return
    order = sorted(names)
    random.Random(20261002).shuffle(order)
    split = {"dev": sorted(order[:4]), "test": sorted(order[4:8]), "sealed": sorted(order[8:])}
    split["sha256"] = {n: hashlib.sha256((OUT / f"{n}.txt").read_bytes()).hexdigest() for n in names}
    (OUT / "split.json").write_text(json.dumps(split, indent=1))
    print({k: v for k, v in split.items() if k != "sha256"})


if __name__ == "__main__":
    main()
