"""Level solver: searches the real simulation for a way to the chest.

Used to guarantee that every training level is solvable *for the bot*
(same action set, same action repeat), and to check hand-made levels.

Weighted A* search: priority = frames used so far + weight * (frames still
needed at full running speed to reach the chest). States that are (almost)
identical to an already seen one are skipped.
A found solution is a real, replayable action list - so "solvable" is never
a guess. "Not solved" can in rare cases mean "search budget too small".

CLI:
    python -m jumpnrun.levelgen.solver levels/exam/level.txt [--video out.mp4]
"""

from __future__ import annotations

import argparse
import heapq
import itertools
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from jumpnrun.core.actions import ACTION_REPEAT, BOT_ACTIONS
from jumpnrun.core.constants import PLAYER_SPEED, TILE
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Simulation, Status


@dataclass
class SolveResult:
    solved: bool
    actions: Optional[List[int]]  # bot action indices (each repeated ACTION_REPEAT frames)
    expanded: int
    max_x: int
    seconds: float


def _state_key(sim: Simulation) -> tuple:
    p = sim.player
    nearby = tuple(
        (e.x // 30, e.y // 30, e.direction)
        for e in sim.enemies
        if abs(e.x - p.x) < 300 and abs(e.y - p.y) < 240
    )
    return (p.x // 8, p.y // 6, p.vy, p.shoot_cooldown > 0, len(sim.enemies), nearby)


def solve(
    level: Level,
    max_expansions: int = 200_000,
    action_repeat: int = ACTION_REPEAT,
    weight: float = 1.5,
    start: Optional[Simulation] = None,
    goal: Optional[Tuple[int, int]] = None,
) -> SolveResult:
    """Search for the chest - or, with `goal=(col, row)`, for standing on that tile's top."""

    start_time = time.time()
    root = start.clone() if start is not None else Simulation(level)
    if goal is None:
        target_x, target_y = level.goal_x, None
    else:
        target_x, target_y = goal[0] * TILE + TILE // 2, goal[1] * TILE  # feet on top of tile (col, row)

    def reached(sim: Simulation) -> bool:
        if goal is None:
            return sim.status == Status.WON
        p = sim.player
        return p.on_ground and p.y + p.h == target_y and abs(p.x + p.w // 2 - target_x) <= TILE

    def priority(sim: Simulation) -> float:
        p = sim.player
        if target_y is None:
            remaining = max(0, target_x - p.x)
        else:
            remaining = abs(target_x - p.x - p.w // 2) + abs(target_y - p.y - p.h)
        return sim.frame + weight * remaining / PLAYER_SPEED

    # node storage for path reconstruction: parent index + action index
    parents: List[int] = [-1]
    via: List[int] = [-1]
    counter = itertools.count()
    heap = [(priority(root), next(counter), 0, root)]
    seen = {_state_key(root)}
    expanded = 0
    best_x = root.player.x

    while heap and expanded < max_expansions:
        _, _, node_id, sim = heapq.heappop(heap)
        expanded += 1
        for action_index, action in enumerate(BOT_ACTIONS):
            child = sim.clone()
            status = child.step(action, frames=action_repeat)
            if status in (Status.DIED_PIT, Status.DIED_ENEMY):
                continue
            parents.append(node_id)
            via.append(action_index)
            child_id = len(parents) - 1
            if reached(child):
                path = []
                while child_id > 0:
                    path.append(via[child_id])
                    child_id = parents[child_id]
                path.reverse()
                return SolveResult(True, path, expanded, child.player.x, time.time() - start_time)
            if status == Status.WON:
                continue  # touched a chest while looking for a waypoint
            key = _state_key(child)
            if key in seen:
                continue
            seen.add(key)
            best_x = max(best_x, child.player.x)
            heapq.heappush(heap, (priority(child), next(counter), child_id, child))

    return SolveResult(False, None, expanded, best_x, time.time() - start_time)


def solve_via(
    level: Level,
    waypoints: Sequence[Tuple[int, int]],
    max_expansions: int = 200_000,
    weight: float = 1.5,
    action_repeat: int = ACTION_REPEAT,
) -> SolveResult:
    """Solve a long level in legs: waypoint -> waypoint -> chest (enemies stay simulated).

    The result is still one real, replayable action list from the level start.
    """

    start_time = time.time()
    sim = Simulation(level)
    actions: List[int] = []
    expanded = 0
    for goal in list(waypoints) + [None]:
        leg = solve(level, max_expansions, action_repeat=action_repeat, weight=weight, start=sim, goal=goal)
        expanded += leg.expanded
        if not leg.solved:
            return SolveResult(False, None, expanded, max(sim.player.x, leg.max_x), time.time() - start_time)
        for action_index in leg.actions:
            sim.step(BOT_ACTIONS[action_index], frames=action_repeat)
        actions += leg.actions
    return SolveResult(True, actions, expanded, sim.player.x, time.time() - start_time)


def reachable_map(level: Level, max_expansions: int = 400_000, action_repeat: int = ACTION_REPEAT) -> str:
    """Level as text with every tile the player can stand on marked '*' (enemies ignored).

    A level-design helper: unreachable platforms have no '*'.
    """

    lines = level.to_text().split("\n")[: level.rows]
    no_enemies = Level([line.replace("E", " ") for line in lines], name=level.name)
    root = Simulation(no_enemies)
    queue = [root]
    seen = {_state_key(root)}
    stood = set()
    expanded = 0
    while queue and expanded < max_expansions:
        sim = queue.pop()
        expanded += 1
        for action in BOT_ACTIONS:
            child = sim.clone()
            if child.step(action, frames=action_repeat) != Status.RUNNING:
                continue
            p = child.player
            if p.on_ground:
                stood.add(((p.x + p.w // 2) // TILE, (p.y + p.h) // TILE - 1))
            key = _state_key(child)
            if key not in seen:
                seen.add(key)
                queue.append(child)
    grid = [list(line.ljust(level.cols)) for line in lines]
    for col, row in stood:
        if 0 <= row < level.rows and 0 <= col < level.cols and grid[row][col] == " ":
            grid[row][col] = "*"
    return "\n".join("".join(row).replace(" ", ".") for row in grid)


def replay(level: Level, actions: List[int], action_repeat: int = ACTION_REPEAT) -> Simulation:
    """Replay a bot action list on a fresh simulation (deterministic)."""

    sim = Simulation(level)
    for action_index in actions:
        sim.step(BOT_ACTIONS[action_index], frames=action_repeat)
    return sim


def _record(level: Level, actions: List[int], path: str, action_repeat: int = ACTION_REPEAT) -> None:
    from jumpnrun.render.renderer import Renderer
    from jumpnrun.render.video import VideoWriter, init_headless

    surface = init_headless()
    renderer = Renderer()
    sim = Simulation(level)
    with VideoWriter(path) as video:
        for action_index in actions:
            for _ in range(action_repeat):
                sim.step(BOT_ACTIONS[action_index])
                renderer.draw(surface, sim)
                video.add(surface)
        for end_frame in range(45):
            renderer.draw(surface, sim, end_frame)
            video.add(surface)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether a level is solvable for the bot.")
    parser.add_argument("levels", nargs="+")
    parser.add_argument("--budget", type=int, default=200_000)
    parser.add_argument("--weight", type=float, default=1.5, help="A* weight (1 = optimal path, higher = faster search)")
    parser.add_argument("--video", help="record the found solution as mp4 (first level only)")
    parser.add_argument("--map", action="store_true", help="print where the player can stand (level design help)")
    parser.add_argument("--via", nargs="*", default=[], metavar="COL,ROW",
                        help="waypoints (tile the player must stand on) for long levels")
    args = parser.parse_args()

    for i, path in enumerate(args.levels):
        level = Level.from_file(path)
        if args.map:
            print(reachable_map(level, max_expansions=args.budget))
            continue
        if args.via:
            waypoints = [tuple(int(v) for v in wp.split(",")) for wp in args.via]
            result = solve_via(level, waypoints, max_expansions=args.budget, weight=args.weight)
        else:
            result = solve(level, max_expansions=args.budget, weight=args.weight)
        verdict = "SOLVED" if result.solved else "NOT SOLVED"
        extra = f"{len(result.actions)} steps" if result.solved else f"reached x={result.max_x}/{level.goal_x}"
        print(f"{path}: {verdict} ({extra}, {result.expanded} expansions, {result.seconds:.1f}s)")
        if args.video and i == 0 and result.solved:
            _record(level, result.actions, args.video)
            print(f"  video: {args.video}")


if __name__ == "__main__":
    main()
