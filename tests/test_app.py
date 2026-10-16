"""Game app (headless): save game, stars, ghost replay, level index, bot opponent, a full play-through of the menus."""

import importlib.util
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from jumpnrun.app import audio, progress as pg
from jumpnrun.app.levels_index import random_entry, scan
from jumpnrun.core.actions import BOT_ACTIONS_V3
from jumpnrun.core.constants import FPS
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Simulation, Status
from jumpnrun.editor.model import load_solution

BERG = "levels/test_serie/berg.txt"


def solution_frames(path):
    """The stored bot solution as one Action per frame (what a perfect human would press)."""

    return [BOT_ACTIONS_V3[a] for a in load_solution(path) for _ in range(2)]


def test_inputs_round_trip_and_replay_exactly():
    actions = solution_frames(BERG)
    codes = [pg.encode_action(a) for a in actions]
    assert pg.decode_inputs(pg.encode_inputs(codes)) == codes
    level = Level.from_file(BERG)
    a, b = Simulation(level), Simulation(level)
    for act, code in zip(actions, codes):
        a.step(act)
        b.step(pg.decode_action(code))
    assert a.status == b.status == Status.WON and a.state_signature() == b.state_signature()


def test_progress_best_times_stars_and_settings(tmp_path):
    p = pg.Progress(tmp_path / "save.json")
    key = pg.level_key(open(BERG).read())
    r1 = p.record_win(key, 900, [1, 2, 3], par_frames=700)
    assert r1["best"] and r1["stars"] == 2
    r2 = p.record_win(key, 1100, [1], par_frames=700)
    assert not r2["best"] and r2["stars"] == 1
    p.settings["music"] = 0.1
    p.save()
    q = pg.Progress(tmp_path / "save.json")
    assert q.best_frames(key) == 900 and q.stars(key) == 2 and q.ghost(key) == [1, 2, 3]
    assert q.settings["music"] == 0.1
    assert pg.stars_for(700, 700) == 3 and pg.stars_for(1100, 700) == 1
    assert pg.format_time(FPS * 61 + 15) == "1:01.50"
    # an edited level gets a new key
    assert pg.level_key(open(BERG).read() + "\n\n") == key
    assert pg.level_key(open(BERG).read().replace("B", " ", 1)) != key


def test_race_win_earns_stars(tmp_path):
    p = pg.Progress(tmp_path / "save.json")
    assert p.record_race("k", False, 600, par_frames=700)["stars"] == 0 and p.stars("k") == 0
    assert p.record_race("k", True, 700, par_frames=700)["stars"] == 3
    p.record_race("k", True, 1100, par_frames=700)  # a slower win keeps the stars
    q = pg.Progress(tmp_path / "save.json")
    assert q.stars("k") == 3 and q.get("k")["race_wins"] == 2 and q.get("k")["races"] == 3
    assert q.best_frames("k") is None  # races do not set the single-player best time or ghost


def test_level_index_tabs_and_par_times():
    tabs = scan()
    assert {"Einstieg", "Handgebaut", "Test-Serie", "Prüfung", "Eigene"} <= set(tabs)
    exam = next(e for e in tabs["Prüfung"] if e.title == "Das Prüfungslevel")
    assert exam.par_proven and 70 * FPS < exam.par_frames < 80 * FPS
    r = random_entry(5, 42)
    assert r.level().chests and r.par_frames > 0 and not r.par_proven
    assert random_entry(5, 42).key == r.key  # same tier + seed = same level


def test_audio_synthesis():
    fx = audio.effects()
    assert {"jump", "shoot", "stomp", "win", "lose", "beep", "go"} <= set(fx)
    assert all(abs(w).max() <= 1.0 for w in fx.values())
    loop = audio.music("game")
    assert 10 < len(loop) / audio.RATE < 20 and abs(loop).max() <= 1.0


torch_missing = not all(importlib.util.find_spec(m) for m in ("torch", "stable_baselines3"))


@pytest.mark.skipif(torch_missing, reason="PyTorch / stable-baselines3 not installed")
def test_bot_racer_wins_and_respects_the_head_start():
    from jumpnrun.app.bot import BotBrain, BotRacer

    brain = BotBrain()
    brain.start()
    assert brain.wait(120), brain.error
    racer = BotRacer(brain.model, Level.from_file("levels/showcase/luecken.txt"), delay_frames=2 * FPS)
    for _ in range(2 * FPS):
        racer.step()
    assert racer.sim.frame == 0  # still waiting
    while not racer.won and racer.frame < 60 * FPS:
        racer.step()
    assert racer.won and racer.finish_frame < 30 * FPS


# ------------------------------------------------------------------ full app flow
@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACE_PIRATE_HOME", str(tmp_path))
    from jumpnrun.app.main import GameApp

    pygame.init()
    screen = pygame.display.set_mode((1520, 800))  # (SCALED needs a real renderer for a second window)
    game = GameApp(screen, load_bot=False)
    yield game, screen
    for scene in game.stack:
        if hasattr(scene, "close"):
            scene.close()


def run(game, screen, seconds, dt=1 / 60):
    for _ in range(int(seconds / dt)):
        game.update(dt)
    game.draw(screen)


def key(game, k):
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))


def test_menu_to_level_to_result_with_best_time_and_ghost(app, monkeypatch):
    from jumpnrun.app import scenes

    game, screen = app
    run(game, screen, 2.5)
    assert type(game.top).__name__ == "MenuScene"
    assert not game.top.buttons[1].enabled  # bot switched off in this test
    game.top.activate("single")
    run(game, screen, 0.5)
    select = game.top
    assert type(select).__name__ == "LevelSelectScene"
    select.tabs.index = select.tabs.labels.index("Test-Serie")
    select.selected = [e.path.stem for e in select.entries].index("berg")
    frames = iter(solution_frames(BERG))
    monkeypatch.setattr(scenes, "keys_to_action", lambda pressed: next(frames, BOT_ACTIONS_V3[0]))
    key(game, pygame.K_RETURN)
    run(game, screen, 0.5)
    play = game.top
    assert type(play).__name__ == "GameScene"
    run(game, screen, 3.2 + 30)  # countdown + the run (the bot's way takes ~25 s)
    assert play.sim.status == Status.WON
    result = game.top
    assert type(result).__name__ == "ResultScene" and result.won
    assert result.stars == 3  # as fast as the proven bot way
    assert game.progress.best_frames(play.entry.key) == play.sim.frame
    result.activate("again")
    run(game, screen, 0.5)
    again = game.top
    assert again.ghost is not None  # the best run now runs along as a ghost
    key(game, pygame.K_ESCAPE)
    run(game, screen, 0.2)
    assert type(game.top).__name__ == "PauseScene"
    game.top.activate("settings")
    run(game, screen, 0.2)
    key(game, pygame.K_ESCAPE)
    game.top.activate("menu")
    run(game, screen, 0.5)
    assert type(game.top).__name__ == "MenuScene"


def test_random_tab_and_editor_scene(app):
    game, screen = app
    run(game, screen, 2.5)
    game.top.activate("single")
    run(game, screen, 0.5)
    select = game.top
    select.tabs.index = len(select.tabs.labels) - 1
    key(game, pygame.K_RIGHT)
    assert select.random.tier == game.random_tier and select.entry is select.random
    run(game, screen, 0.1)
    key(game, pygame.K_ESCAPE)
    run(game, screen, 0.5)
    game.top.activate("editor")
    run(game, screen, 0.5)
    assert type(game.top).__name__ == "EditorScene"
    key(game, pygame.K_ESCAPE)  # unchanged level: back to the menu without asking
    run(game, screen, 0.5)
    assert type(game.top).__name__ == "MenuScene"
