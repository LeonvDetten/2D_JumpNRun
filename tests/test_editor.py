"""Level editor: grid model, file round trip, proven way (cut on edits, continue), app clicks (headless)."""

import json
import os
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from jumpnrun.core.actions import BOT_ACTIONS_V3
from jumpnrun.core.constants import TILE
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Simulation, Status
from jumpnrun.editor import proof as pf
from jumpnrun.editor.model import LevelModel, is_protected, load_solution, solution_path
from jumpnrun.levelgen.solver import solve_path_legs

WALL = "\n".join([""] * 9 + ["      B", "      B    C", " P    B", "BBBBBBBBBBBB"])  # as in test_levelgen


def exam_with(edits):
    model = LevelModel.from_file("levels/exam/level.txt")
    keeper = pf.ProofKeeper(model)
    keeper.load(load_solution(model.path))
    for col, row, ch in edits:
        model.set(col, row, ch)
    keeper.revalidate()
    return model, keeper


def exam_path_cell(step):
    """(col, row) the exam solution's player stands in after `step` actions (2 frames each)."""

    level = Level.from_file("levels/exam/level.txt")
    sim = Simulation(level)
    for a in load_solution("levels/exam/level.txt")[:step]:
        sim.step(BOT_ACTIONS_V3[a], frames=2)
    p = sim.player
    return (p.x + p.w // 2) // TILE, (p.y + p.h - 1) // TILE


# ------------------------------------------------------------------ model
def test_every_level_file_round_trips_byte_for_byte():
    for path in sorted(Path("levels").rglob("*.txt")):
        with open(path, newline="") as f:
            assert LevelModel.from_file(path).to_text() == f.read(), path


def test_saving_an_edit_changes_only_that_row(tmp_path):
    src = Path("levels/exam/level.txt")
    model = LevelModel.from_file(src)
    model.set(40, 0, "B")
    model.save(tmp_path / "x.txt")
    old = src.read_text().split("\n")
    new = (tmp_path / "x.txt").read_text().split("\n")
    assert [i for i, (a, b) in enumerate(zip(old, new)) if a != b] == [0]
    assert Level.from_file(tmp_path / "x.txt").is_solid(40, 0)


def test_painting_undo_redo_and_one_start():
    model = LevelModel()
    assert not model.dirty
    model.set(5, 5, "P")
    assert model.find("P") == [(5, 5)]  # the default start was replaced
    model.begin()
    for col in range(10, 14):
        model.set(col, 8, "B")
    model.end()
    assert model.dirty
    model.undo()  # the whole stroke at once
    assert all(model.get(col, 8) == " " for col in range(10, 14))
    model.redo()
    assert model.get(12, 8) == "B"
    model.undo()
    model.undo()
    assert not model.dirty  # back at the saved state


def test_level_grows_and_columns_insert_and_delete():
    model = LevelModel()
    width = model.width
    model.set(width + 5, 3, "C")
    assert model.width == width + 6
    model.insert_column(0)
    assert model.get(width + 6, 3) == "C" and model.find("P") == [(3, 11)]
    model.delete_column(0)
    assert model.find("P") == [(2, 11)]
    model.fill(0, 0, 3, 1, "B")
    assert sum(row.count("B") for row in model.grid[:2]) == 8
    assert LevelModel(WALL.replace("C", " ")).problems()


def test_measuring_levels_are_protected():
    assert is_protected("levels/exam/level.txt")
    assert is_protected("levels/validierung/v2/x.txt")
    assert is_protected("levels/test_serie/berg.txt")
    assert not is_protected("levels/phase1/p1_luecken_01.txt")
    assert not is_protected("levels/eigene/neu.txt")


# ------------------------------------------------------------------ proven way
def test_stored_exam_solution_is_a_complete_proof():
    _, keeper = exam_with([])
    assert keeper.state == pf.COMPLETE and keeper.proof.complete
    assert len(keeper.proof) >= 2 * len(json.load(open("levels/exam/level.loesung.json"))) - 1  # won mid-action


def test_a_block_the_way_never_touches_cuts_nothing():
    _, keeper = exam_with([(60, 0, "B")])
    assert keeper.state == pf.COMPLETE and keeper.proof.complete


def test_a_wall_on_the_way_cuts_it_right_there():
    col, row = exam_path_cell(600)
    _, keeper = exam_with([(col + 2, row, "B"), (col + 2, row - 1, "B")])
    assert keeper.state == pf.CHANGED and not keeper.proof.complete
    assert 560 < len(keeper.proof) <= 612
    assert col - 2 <= keeper.proven_col <= col + 2


def test_path_legs_continue_from_a_mid_level_state():
    level = Level.from_file("levels/test_serie/berg.txt")
    actions = load_solution("levels/test_serie/berg.txt")
    start = Simulation(level)
    for a in actions[:200]:
        start.step(BOT_ACTIONS_V3[a], frames=2)
    legs = []
    r = solve_path_legs(level, action_repeat=2, leg_budget=20_000, total_budget=120_000, start=start, on_leg=legs.append)
    assert r.solved and legs and legs[-1] == r.actions[: len(legs[-1])]
    sim = Simulation(level)
    for a in actions[:200] + r.actions:
        sim.step(BOT_ACTIONS_V3[a], frames=2)
    assert sim.status == Status.WON


def wait(keeper, seconds=60):
    t = time.time()
    while keeper.job is not None and time.time() - t < seconds:
        keeper.update()
        time.sleep(0.05)
    assert keeper.job is None


def test_check_proves_a_new_level_and_marks_an_impossible_one():
    keeper = pf.ProofKeeper(LevelModel())
    keeper.check()
    wait(keeper)
    assert keeper.state == pf.COMPLETE and keeper.proof.complete
    wall = pf.ProofKeeper(LevelModel(WALL))
    wall.check()
    wait(wall)
    assert wall.state == pf.STUCK and wall.stuck_x // TILE in (4, 5)
    wall.check()  # unchanged: retried with a bigger budget
    assert wall.budget == 2 * pf.BASE_BUDGET
    wall.stop()


class FakeWorker:
    def __init__(self, msgs):
        self.msgs = list(msgs)
        self.alive = True

    def messages(self):
        out, self.msgs = self.msgs, []
        return out

    def stop(self):
        self.alive = False


def test_an_edit_inside_the_checked_part_ends_the_check_there():
    model, keeper = exam_with([])
    actions = keeper.proof.actions
    keeper.proof = pf.Proof()  # pretend nothing is proven and a check from the start is running
    keeper.state = pf.RUNNING
    worker = FakeWorker([("leg", actions[:700])])
    keeper.job = pf.Job(model.to_text(), model.version, 0, pf.BASE_BUDGET, worker)
    keeper.update()
    assert len(keeper.proof) == 700 and keeper.state == pf.RUNNING
    col, row = exam_path_cell(400)  # build a wall into the part that is already proven
    model.set(col + 2, row, "B")
    model.set(col + 2, row - 1, "B")
    keeper.revalidate()
    assert keeper.job is None and not worker.alive
    assert keeper.state == pf.CHANGED and 350 < len(keeper.proof) <= 412
    # a leg found on the old level is cut where the edit starts
    keeper.state = pf.RUNNING
    worker2 = FakeWorker([("leg", actions[:900])])
    keeper.job = pf.Job(Level.from_file("levels/exam/level.txt").to_text(), model.version - 2, 0, pf.BASE_BUDGET, worker2)
    keeper.update()
    assert keeper.state == pf.CHANGED and len(keeper.proof) <= 412 and not worker2.alive


# ------------------------------------------------------------------ app (headless)
@pytest.fixture
def app():
    from jumpnrun.editor.app import EditorApp

    pygame.init()
    screen = pygame.display.set_mode((1520, 800))
    editor = EditorApp(None, (1520, 800))
    yield editor, screen
    editor.keeper.stop()


def click(editor, pos, button=1):
    pygame.mouse.set_pos(pos)
    editor.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=pos))
    editor.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, button=button, pos=pos))


def cell_pos(editor, col, row):
    return editor.col_x(col) + editor.z // 2, editor.level_top + row * editor.z + editor.z // 2


def test_app_select_tool_paint_check_and_save(app, tmp_path):
    editor, screen = app
    enemy_button = next(b for b in editor.tool_buttons if b.key == "enemy")
    click(editor, enemy_button.rect.center)
    assert editor.tool == "enemy"
    click(editor, cell_pos(editor, 15, 11))
    assert editor.model.get(15, 11) == "E"
    click(editor, cell_pos(editor, 15, 11), button=3)  # right click erases
    assert editor.model.get(15, 11) == " "
    editor.update(1.0)
    editor.do("check")
    t = time.time()
    while editor.keeper.job is not None and time.time() - t < 60:
        editor.update(0.05)
        time.sleep(0.05)
    assert editor.keeper.state == pf.COMPLETE
    editor.draw(screen)
    target = tmp_path / "mein_level.txt"
    editor._write(target)
    assert Level.from_file(target).chests
    sol = json.loads(solution_path(target).read_text())
    assert sol["action_repeat"] == 2 and sol["actions"] == editor.keeper.proof.actions
    assert not editor.model.dirty


def test_app_never_overwrites_the_exam(app):
    editor, screen = app
    before = Path("levels/exam/level.txt").read_bytes()
    editor.open(Path("levels/exam/level.txt"))
    click(editor, cell_pos(editor, 3, 0))
    editor.do("save")
    assert type(editor.dialog).__name__ == "SaveAsDialog"
    editor.draw(screen)
    assert Path("levels/exam/level.txt").read_bytes() == before
