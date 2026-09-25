"""PIRATE GAME
    This is a 2D game where the player has to fight against enemies and jump through the world.

    Module name:
            game.py

    Doc:
            Human play: reads the keyboard, feeds it into the deterministic game core
            (jumpnrun.core) and draws every frame with the renderer. The bot plays the
            exact same simulation, just with actions from the neural network.

    Usage:
            python game.py [path/to/level.txt]

    Controls:
            A / D or arrow keys   walk
            W / SPACE / UP        jump
            ENTER                 shoot
            R                     restart
            ESC                   quit

        author: Leon von Detten
        date: 19.04.2023 (core rewrite 2026)
        license: free
"""

import os
import sys

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame

from jumpnrun.core import Action, Level, Simulation, Status
from jumpnrun.core.constants import FPS, SCREEN_H, SCREEN_W
from jumpnrun.render.renderer import Renderer

DEFAULT_LEVEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels", "exam", "level.txt")


def action_from_keys(pressed) -> Action:
    """Map the pygame key state to one Action (same input the bot produces)."""

    return Action(
        left=bool(pressed[pygame.K_a] or pressed[pygame.K_LEFT]),
        right=bool(pressed[pygame.K_d] or pressed[pygame.K_RIGHT]),
        jump=bool(pressed[pygame.K_w] or pressed[pygame.K_SPACE] or pressed[pygame.K_UP]),
        shoot=bool(pressed[pygame.K_RETURN]),
    )


def main(level_path: str = DEFAULT_LEVEL) -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("2D Game")
    clock = pygame.time.Clock()

    sim = Simulation(Level.from_file(level_path))
    renderer = Renderer()
    frames_since_end = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                sim.reset()
                frames_since_end = 0

        if sim.status == Status.RUNNING:
            sim.step(action_from_keys(pygame.key.get_pressed()))
        else:
            frames_since_end += 1

        renderer.draw(screen, sim, frames_since_end)
        pygame.display.update()
        clock.tick(FPS)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LEVEL)
