"""Phase 9: path distance to the chest for every place the player can stand.

    from jumpnrun.levelgen.distmap import DistanceMap
    dm = DistanceMap(level)
    dm.at_player(sim.player)      # tiles still to go along the way (None = not on a known standing place)

A tile graph over standing places (an empty tile with a block below). Edges are the moves the bot can make:
walking one tile, stepping off an edge and falling, and the jumps measured once with the solver
(`jump_catalog.json`, mirrored for both directions). A backwards Dijkstra from the chest gives each standing
place its remaining way in tiles. Unlike "x so far", the distance grows on a dead-end road and shrinks when the
player turns back or drops down - so turning around is finally rewarded.

Only a training signal: the bot never sees this map, and nothing of it is computed for evaluation.
Approximate on purpose (enemies ignored, jump arcs simplified); a few milliseconds per level.
"""

from __future__ import annotations

import heapq
import json
from typing import Dict, List, Optional, Tuple

from jumpnrun.core.constants import ROWS, TILE
from jumpnrun.core.level import Level
from jumpnrun.levelgen.jump_catalog import CATALOG_PATH

Cell = Tuple[int, int]  # (col, row) of the tile the player's body is in
FALL_DRIFT = 1  # extra columns of sideways drift while falling off an edge


def _jumps() -> List[Tuple[int, int]]:
    """(gap, drop) pairs the bot can make from a standing start (any takeoff/landing width)."""

    pairs = {(j["gap"], j["drop"]) for j in json.loads(CATALOG_PATH.read_text())}
    deepest = max(d for _, d in pairs)
    for gap, drop in list(pairs):
        if drop == deepest:  # deeper drops are at least as wide
            pairs |= {(gap, d) for d in range(drop + 1, ROWS)}
    return sorted(pairs)


JUMPS = _jumps()


class DistanceMap:
    def __init__(self, level: Level):
        self.level = level
        self.cols = level.cols
        solid = level.solid
        self._solid = solid

        def free(c: int, r: int) -> bool:
            if c < 0 or c >= self.cols:
                return False
            return r < 0 or (r < ROWS and not solid[r][c])

        self._free = free
        self.stand = {(c, r) for c in range(self.cols) for r in range(ROWS - 1) if not solid[r][c] and solid[r + 1][c]}
        self.edges: Dict[Cell, List[Tuple[Cell, float]]] = {u: [] for u in self.stand}
        for u in self.stand:
            self._moves(u)
        targets = self._targets()
        self.dist: Dict[Cell, float] = {}
        self.reachable = bool(targets)
        if targets:
            self._dijkstra(targets)
        self.start = None
        if self.reachable:
            x, y = level.spawn
            self.start = self.at_xy(x, y, 40, 60)
            if self.start is None:  # spawn in the air: where the player lands
                self.start = self.below(x, y, 40, 60)

    # ---------------------------------------------------------------- graph
    def _add(self, u: Cell, v: Cell, cost: float) -> None:
        if v in self.stand and v != u:
            self.edges[u].append((v, cost))

    def _fall_from(self, col: int, row: int) -> Optional[int]:
        """Row where a player falling in `col` from body row `row` comes to stand (None = pit)."""

        r = row
        while r < ROWS - 1:
            if not self._free(col, r):
                return None
            if not self._free(col, r + 1):
                return r
            r += 1
        return None

    def _moves(self, u: Cell) -> None:
        c, r = u
        free = self._free
        for d in (-1, 1):
            n = c + d
            if not free(n, r):
                if free(c, r - 1) and (n, r - 1) in self.stand and free(c, r - 2) and free(n, r - 2):
                    self._add(u, (n, r - 1), 1.3)  # one step up (stairs)
                continue
            if (n, r) in self.stand:
                self._add(u, (n, r), 1.0)
            else:  # step off the edge and fall, maybe drifting a little further
                for k in range(FALL_DRIFT + 1):
                    col = n + d * k
                    if k and not all(free(col, rr) for rr in (r, r + 1)):
                        break
                    land = self._fall_from(col, r)
                    if land is not None:
                        self._add(u, (col, land), 1.0 + k + 0.3 * (land - r))
            if not free(c, r - 1):
                continue  # no room to jump
            for gap, drop in JUMPS:
                lc, lr = c + d * (gap + 1), r + drop
                if (lc, lr) not in self.stand:
                    continue
                if drop < 0:  # one row up: the head passes through row r - 2
                    ok = free(c, r - 2) and all(free(c + d * k, rr) for k in range(1, gap + 1) for rr in (r - 2, r - 1, r)) \
                        and free(lc, r - 2) and free(lc, r - 1)
                else:
                    ok = all(free(c + d * k, rr) for k in range(1, gap + 1) for rr in (r - 1, r)) \
                        and all(free(lc, rr) for rr in range(r - 1, lr + 1))
                if ok:
                    self._add(u, (lc, lr), gap + 1 + 0.3 * abs(drop))

    def _targets(self) -> List[Cell]:
        out = []
        for cx, cy, cw, _ in self.level.chests:
            col, row = cx // TILE, min(ROWS - 1, cy // TILE)
            for c in range(col - 1, col + 2):
                if (c, row) in self.stand:
                    out.append((c, row))
        return out

    def _dijkstra(self, targets: List[Cell]) -> None:
        back: Dict[Cell, List[Tuple[Cell, float]]] = {u: [] for u in self.stand}
        for u, out in self.edges.items():
            for v, cost in out:
                back[v].append((u, cost))
        heap = [(0.0, t) for t in targets]
        for t in targets:
            self.dist[t] = 0.0
        while heap:
            d, v = heapq.heappop(heap)
            if d > self.dist.get(v, float("inf")):
                continue
            for u, cost in back[v]:
                nd = d + cost
                if nd < self.dist.get(u, float("inf")):
                    self.dist[u] = nd
                    heapq.heappush(heap, (nd, u))

    # --------------------------------------------------------------- lookup
    def at_xy(self, x: int, y: int, w: int, h: int) -> Optional[float]:
        """Distance for a body at (x, y, w, h) standing on something; None if unknown."""

        row = (y + h - 1) // TILE
        best = None
        for col in {(x + w // 2) // TILE, x // TILE, (x + w - 1) // TILE}:
            d = self.dist.get((col, row))
            if d is not None and (best is None or d < best):
                best = d
        return best

    def below(self, x: int, y: int, w: int, h: int) -> Optional[float]:
        """Distance of the first standing place below a body in the air (search guidance; None over a pit)."""

        col = (x + w // 2) // TILE
        for row in range(max(0, (y + h - 1) // TILE), ROWS - 1):
            if (col, row) in self.stand:
                return self.dist.get((col, row))
            if self._solid[row][col] if 0 <= col < self.cols else True:
                return None
        return None

    def at_player(self, player) -> Optional[float]:
        if not player.on_ground:
            return None
        return self.at_xy(player.x, player.y, player.w, player.h)

    def text(self) -> str:
        """Debug view: distances (mod 10) on standing places, '#' blocks, '-' standing places with no way on."""

        lines = []
        for r in range(ROWS):
            row = []
            for c in range(self.cols):
                if self._solid[r][c]:
                    row.append("#")
                elif (c, r) in self.dist:
                    row.append(str(int(self.dist[(c, r)]) % 10))
                elif (c, r) in self.stand:
                    row.append("-")
                else:
                    row.append(" ")
            lines.append("".join(row))
        return "\n".join(lines)
