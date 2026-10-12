"""The "proven way" of the level editor: a real bot action list that plays from the start to some point.

    keeper = ProofKeeper(model)
    keeper.check()        # button "Prüfen": search in a background process, from the end of the proven way
    keeper.update()       # every frame: take over solved legs / the result
    keeper.revalidate()   # after edits: cut the way where the edit changes what happens

Only a found way is a proof. "No way found" can also mean "search budget too small" (the solver did not
find the exam level from scratch), so a repeated check without changes searches with twice the budget.

A way stays valid as long as replaying it on the current level gives exactly the same states as on the level it
was found for (player, awake enemies, bullets). A block in the sky the way never touches cuts nothing; a block
that changes how an enemy walks cuts the way where the difference starts.
"""

from __future__ import annotations

import multiprocessing as mp
import queue as queue_lib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from jumpnrun.core.actions import BOT_ACTIONS_V3
from jumpnrun.core.constants import TILE
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Simulation, Status

REPEAT = 2  # frames per bot action (as the current bots and stored solutions)
BACKOFF = 15  # steps (1 s) a continued check starts before the end of the proven way
BASE_BUDGET = 120_000  # solver expansions per check (like the phase 12/13 demo search)
MAX_BUDGET = 960_000


def signature(sim: Simulation) -> tuple:
    """State that decides the rest of the game. Sleeping enemies are left out: they only start to matter
    when they wake up (and then they are compared), so an edit far ahead does not cut the way."""

    p = sim.player
    return (
        sim.frame,
        sim.status,
        (p.x, p.y, p.vx, p.vy, p.on_ground, p.facing, p.shoot_cooldown),
        tuple((e.x, e.y, e.vy, e.direction) for e in sim.enemies if e.active),
        tuple((b.x, b.y, b.direction) for b in sim.bullets),
    )


@dataclass
class Trace:
    actions: List[int]
    sigs: List[tuple]  # sigs[i] = state after i actions
    points: List[Tuple[int, int]]  # player centre after i actions (pixels)
    won: bool


def trace(level: Level, actions: List[int]) -> Trace:
    """Replay `actions`; stops at the win (later actions are dropped) or at a death (that action too)."""

    sim = Simulation(level)
    sigs, points = [signature(sim)], [_centre(sim)]
    done: List[int] = []
    for a in actions:
        sim.step(BOT_ACTIONS_V3[a], frames=REPEAT)
        if sim.status in (Status.DIED_PIT, Status.DIED_ENEMY):
            break
        done.append(a)
        sigs.append(signature(sim))
        points.append(_centre(sim))
        if sim.status == Status.WON:
            break
    return Trace(done, sigs, points, sim.status == Status.WON)


def _centre(sim: Simulation) -> Tuple[int, int]:
    p = sim.player
    return p.x + p.w // 2, p.y + p.h // 2


@dataclass
class Proof:
    actions: List[int] = field(default_factory=list)
    sigs: List[tuple] = field(default_factory=list)
    points: List[Tuple[int, int]] = field(default_factory=list)
    complete: bool = False

    @classmethod
    def found(cls, level: Level, actions: List[int]) -> "Proof":
        """A way found on `level` (replayed there to record its states)."""

        t = trace(level, actions)
        return cls(t.actions, t.sigs, t.points, t.won)

    def __len__(self) -> int:
        return len(self.actions)

    def revalidate(self, level: Level) -> int:
        """Keep the way only as far as it still plays the same on `level`; returns the new length."""

        t = trace(level, self.actions)
        if t.won:  # still (or now) reaches the chest: a full proof, whatever changed on the way
            self.actions, self.sigs, self.points, self.complete = t.actions, t.sigs, t.points, True
            return len(self.actions)
        k = 0
        if self.sigs and t.sigs[0] == self.sigs[0]:
            while k < len(t.actions) and k + 1 < len(self.sigs) and t.sigs[k + 1] == self.sigs[k + 1]:
                k += 1
        else:  # the start itself changed
            t.sigs = t.sigs[:1]
            t.points = t.points[:1]
        self.actions, self.sigs, self.points, self.complete = t.actions[:k], t.sigs[: k + 1], t.points[: k + 1], False
        return k

    @property
    def end_point(self) -> Optional[Tuple[int, int]]:
        return self.points[-1] if self.points else None

    @property
    def end_col(self) -> int:
        return self.points[-1][0] // TILE if self.points else 0


# ------------------------------------------------------------------ background search
def _work(text: str, prefix: List[int], budget: int, out) -> None:
    """Runs in its own process: search on from the end of `prefix`, report each solved leg."""

    try:
        from jumpnrun.levelgen.solver import solve, solve_path_legs

        level = Level.from_text(text)
        sim = Simulation(level)
        for a in prefix:
            sim.step(BOT_ACTIONS_V3[a], frames=REPEAT)
        if sim.status == Status.WON:
            out.put(("done", True, list(prefix), sim.player.x))
            return
        if sim.status != Status.RUNNING:
            out.put(("done", False, None, sim.player.x))
            return
        found = list(prefix)

        def on_leg(actions: List[int]) -> None:
            found[:] = list(prefix) + actions
            out.put(("leg", list(found)))

        r = solve_path_legs(level, action_repeat=REPEAT, leg_budget=max(budget // 6, 5_000), total_budget=budget,
                            start=sim, on_leg=on_leg)
        if r.solved:
            out.put(("done", True, list(prefix) + r.actions, r.max_x))
            return
        # fallback: plain search towards the chest from the furthest proven point (the way map behind the
        # leg search is approximate and misses some tight tunnels)
        start = Simulation(level)
        for a in found:
            start.step(BOT_ACTIONS_V3[a], frames=REPEAT)
        r2 = solve(level, max(budget // 2, 20_000), action_repeat=REPEAT, weight=1.5, start=start,
                   actions=BOT_ACTIONS_V3)
        if r2.solved:
            out.put(("done", True, found + r2.actions, r2.max_x))
        else:
            out.put(("done", False, None, max(r.max_x, r2.max_x)))
    except Exception as exc:  # pragma: no cover - reported in the editor's status line
        out.put(("error", f"{type(exc).__name__}: {exc}"))


class Worker:
    """One background search process (spawned, so it works the same on Linux, macOS and Windows)."""

    def __init__(self, text: str, prefix: List[int], budget: int):
        ctx = mp.get_context("spawn")
        self.queue = ctx.Queue()
        self.process = ctx.Process(target=_work, args=(text, list(prefix), budget, self.queue), daemon=True)
        self.process.start()

    def messages(self) -> list:
        out = []
        while True:
            try:
                out.append(self.queue.get_nowait())
            except queue_lib.Empty:
                break
        return out

    @property
    def alive(self) -> bool:
        return self.process.is_alive()

    def stop(self) -> None:
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(timeout=1.0)


# ------------------------------------------------------------------ editor state
NONE, RUNNING, COMPLETE, STUCK, CHANGED, INVALID, ERROR = (
    "none", "running", "complete", "stuck", "changed", "invalid", "error")


@dataclass
class Job:
    text: str
    version: int
    prefix_len: int
    budget: int
    worker: Worker
    reached: int = 0  # length of the longest way this job has reported


class ProofKeeper:
    """Proof state of the level being edited: proven way, running check, last result."""

    def __init__(self, model):
        self.model = model
        self.proof = Proof()
        self.state = NONE
        self.job: Optional[Job] = None
        self.seen_version = -1
        self.level: Optional[Level] = None
        self.stuck_x = 0
        self.stuck_version = -1
        self.budget = BASE_BUDGET
        self.message = ""
        self.revalidate()

    # ------------------------------------------------------------- inputs
    def load(self, actions: Optional[List[int]]) -> None:
        """Take over a stored solution of a freshly opened level."""

        self.stop()
        self.proof = Proof()
        self.state = NONE
        self.budget = BASE_BUDGET
        self.seen_version = -1
        if actions and self._level() is not None:
            self.proof = Proof.found(self.level, actions)
            self.state = COMPLETE if self.proof.complete else (CHANGED if len(self.proof) else NONE)
        self.revalidate()

    def _level(self) -> Optional[Level]:
        try:
            self.level = self.model.to_level()
        except ValueError:
            self.level = None
        return self.level

    def revalidate(self) -> None:
        """Bring the proven way up to date with the edited level (call when the model changed)."""

        if self.seen_version == self.model.version:
            return
        self.seen_version = self.model.version
        if self._level() is None:
            self.stop()
            self.state = INVALID
            return
        if self.state == INVALID:
            self.state = NONE
        before = len(self.proof)
        was_complete = self.proof.complete
        self.proof.revalidate(self.level)
        if self.proof.complete:
            self.stop()
            self.state = COMPLETE
            return
        if self.job is not None:
            if len(self.proof) < max(self.job.reached, self.job.prefix_len):
                self.stop()  # the part this check already did has changed: it ends here
                self.state = CHANGED
            return
        if self.state in (COMPLETE, STUCK) or len(self.proof) < before or was_complete:
            self.state = CHANGED if len(self.proof) else NONE

    def check(self) -> str:
        """Button "Prüfen". Returns a short note for the status line."""

        self.revalidate()
        if self.state == INVALID:
            return "Erst eine Kiste setzen."
        if self.job is not None:
            return "Prüfung läuft schon."
        if self.proof.complete:
            return "Schon bewiesen lösbar."
        retry = self.state == STUCK and self.stuck_version == self.model.version
        self.budget = min(self.budget * 2, MAX_BUDGET) if retry else BASE_BUDGET
        keep = max(0, len(self.proof) - (2 if retry else 1) * BACKOFF)
        text = self.model.to_text()
        self.job = Job(text, self.model.version, keep, self.budget, Worker(text, self.proof.actions[:keep], self.budget))
        self.state = RUNNING
        if retry:
            return f"Gründlicher prüfen (Suchbudget {self.budget // 1000}k)."
        return "Prüfe ab Spalte %d." % (self.proof.points[keep][0] // TILE if self.proof.points else 0)

    def stop(self) -> None:
        if self.job is not None:
            self.job.worker.stop()
            self.job = None
            if self.state == RUNNING:
                self.state = CHANGED if len(self.proof) else NONE

    # ------------------------------------------------------------- results
    def update(self) -> None:
        """Poll the running check (call every frame)."""

        job = self.job
        if job is None:
            return
        for msg in job.worker.messages():
            if self.job is not job:
                return
            kind = msg[0]
            if kind == "leg":
                self._take(job, msg[1])
            elif kind == "done":
                _, solved, actions, max_x = msg
                if solved:
                    self._take(job, actions)
                self._finish(job, solved, max_x)
                return
            elif kind == "error":
                self.job = None
                self.state = ERROR
                self.message = msg[1]
                return
        if self.job is job and not job.worker.alive:
            for msg in job.worker.messages():  # last words before the process ended
                if msg[0] == "done":
                    if msg[1]:
                        self._take(job, msg[2])
                    self._finish(job, msg[1], msg[3])
                    return
            self.job = None
            self.state = ERROR
            self.message = "Prüfprozess unerwartet beendet."

    def _take(self, job: Job, actions: List[int]) -> None:
        """A way found on the job's snapshot: keep it if it is longer, as far as it holds on the current level."""

        new = Proof.found(Level.from_text(job.text), actions)
        job.reached = max(job.reached, len(new))
        if self.seen_version != job.version and self.level is not None:
            new.revalidate(self.level)
        if new.complete or len(new) > len(self.proof):
            self.proof = new
        if len(new) < job.reached and not new.complete:  # cut by an edit: the check ends here
            self.stop()
            self.state = CHANGED

    def _finish(self, job: Job, solved: bool, max_x: int) -> None:
        if self.job is not job:
            return
        job.worker.stop()
        self.job = None
        if self.proof.complete:
            self.state = COMPLETE
        elif solved or self.model.version != job.version:
            self.state = CHANGED  # solved on the snapshot, but edited since
        else:
            self.state = STUCK
            self.stuck_x = max_x
            self.stuck_version = job.version

    # ------------------------------------------------------------- display
    @property
    def proven_col(self) -> int:
        return self.proof.end_col
