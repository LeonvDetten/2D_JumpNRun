"""Rendering smoke tests (headless): drawing must work and never change the game."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from jumpnrun.core import Action, Level, Simulation
from jumpnrun.levelgen.generator import generate
from jumpnrun.render.ghosts import GhostView
from jumpnrun.render.renderer import Renderer
from jumpnrun.render.video import init_headless


def test_renderer_draws_without_changing_the_simulation():
    surface = init_headless()
    sim = Simulation(Level.from_file("levels/exam/level.txt"))
    renderer = Renderer()
    for i in range(60):
        sim.step(Action(right=True, jump=i % 10 == 0, shoot=i == 30))
        before = sim.state_signature()
        renderer.draw(surface, sim)
        assert sim.state_signature() == before


def test_ghost_view_layouts():
    surface = init_headless()
    for level in (generate(0, 0), Level.from_file("levels/showcase/luecken.txt"), generate(7, 0)):
        sims = [Simulation(level) for _ in range(4)]
        for i, sim in enumerate(sims):
            sim.step(Action(right=True), frames=10 * i)
        view = GhostView(level)
        view.draw(surface, sims, [True, True, False, True], [(300, 500)], "Titel", "Untertitel")
