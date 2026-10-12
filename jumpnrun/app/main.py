"""Space Pirate - the game app: loading screen, menu, single player, race against the bot, level editor.

    python spacepirate.py                 # the app
    python spacepirate.py level.txt       # straight into one level (after the loading screen)
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "hide")
import pygame

from jumpnrun.app.bot import BotBrain
from jumpnrun.app.progress import Progress
from jumpnrun.core.constants import SCREEN_H, SCREEN_W

FADE_SECONDS = 0.18


class GameApp:
    def __init__(self, screen: pygame.Surface, start_level: Optional[str] = None, load_bot: bool = True):
        from jumpnrun.app.scenes import LoadingScene

        self.screen = screen
        self.progress = Progress()
        self.bot = BotBrain()
        if not load_bot:
            self.bot.error = "Bot abgeschaltet."
        self.assets = None
        self.audio = _SilentAudio()
        self.logo = None
        self.background = None
        self.tabs = {}
        self.random_tier, self.random_seed = 3, 1
        self.running = True
        self._night = None
        self.stack: List = []
        self._pending = None
        self._fade = 0.0  # >0: fading out to a pending scene, <0: fading in
        then = None
        if start_level:
            then = lambda: self._direct(start_level)  # noqa: E731
        self.stack = [LoadingScene(self, then)]

    # ------------------------------------------------------------- loading steps
    def load_assets(self) -> None:
        from jumpnrun.app.gfx import Logo, SpaceBackground
        from jumpnrun.render.assets import get_assets

        self.assets = get_assets()
        self.logo = Logo(self.assets)
        self.background = SpaceBackground(self.assets.background)
        try:
            pygame.display.set_icon(self.assets.player["IDLE"][1][0])
        except pygame.error:
            pass

    def load_audio(self) -> None:
        from jumpnrun.app.audio import Audio

        self.audio = Audio(self.progress.settings)

    def load_levels(self) -> None:
        from jumpnrun.app.levels_index import scan

        self.tabs = scan()

    def refresh_own_levels(self) -> None:
        from jumpnrun.app.levels_index import scan

        self.tabs["Eigene"] = scan("Eigene").get("Eigene", [])

    def _direct(self, path: str):
        from pathlib import Path

        from jumpnrun.app.levels_index import LevelEntry, par_frames
        from jumpnrun.app.scenes import GameScene
        from jumpnrun.core.level import Level
        from jumpnrun.editor.model import load_solution

        p = Path(path)
        text = p.read_text(encoding="utf-8")
        entry = LevelEntry(p.stem, text, p.parent.name, p)
        solution = load_solution(p)
        entry.par_frames = par_frames(Level.from_text(text), solution)
        entry.par_proven = bool(solution)
        return GameScene(self, entry, "single", 0, "")

    # ------------------------------------------------------------- helpers
    def night_gradient(self) -> pygame.Surface:
        if self._night is None:
            from jumpnrun.app.gfx import vertical_gradient

            self._night = vertical_gradient((SCREEN_W, SCREEN_H), (16, 14, 44, 255), (4, 4, 14, 255))
        return self._night

    def progress_summary(self):
        done = sum(1 for e in self.progress.levels.values() if e.get("best") or e.get("race_wins"))
        stars = sum(e.get("stars", 0) for e in self.progress.levels.values())
        return done, stars

    def set_fullscreen(self, on: bool) -> None:
        self.progress.settings["fullscreen"] = on
        self.progress.save()
        if bool(pygame.display.get_surface().get_flags() & pygame.FULLSCREEN) != on:
            try:
                pygame.display.toggle_fullscreen()
            except pygame.error:
                pass

    # ------------------------------------------------------------- scene stack
    @property
    def top(self):
        return self.stack[-1]

    def switch(self, scene) -> None:
        """Replace the whole stack (with a short fade)."""

        self._pending = scene
        self._fade = max(self._fade, 0.0001)

    def push(self, scene) -> None:
        self.stack.append(scene)
        scene.enter()

    def pop(self) -> None:
        if len(self.stack) > 1:
            self.stack.pop()

    def quit(self) -> None:
        self.running = False

    def _swap(self) -> None:
        for scene in self.stack:
            close = getattr(scene, "close", None)
            if close is not None:
                close()
        self.stack = [self._pending]
        self._pending = None
        self.top.enter()

    # ------------------------------------------------------------- frame
    def handle(self, event) -> None:
        if event.type == pygame.QUIT and type(self.top).__name__ != "EditorScene":
            self.quit()
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            self.set_fullscreen(not self.progress.settings["fullscreen"])
            return
        if self._pending is None:
            self.top.handle(event)

    def update(self, dt: float) -> None:
        if self._pending is not None:
            self._fade += dt / FADE_SECONDS
            if self._fade >= 1.0:
                self._swap()
                self._fade = -1.0
        elif self._fade < 0:
            self._fade = min(0.0, self._fade + dt / FADE_SECONDS)
        self.top.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        first = len(self.stack) - 1
        while first > 0 and self.stack[first].overlay:
            first -= 1
        for scene in self.stack[first:]:
            scene.draw(surface)
        alpha = abs(self._fade)
        if alpha > 0:
            veil = pygame.Surface((SCREEN_W, SCREEN_H))
            veil.fill((0, 0, 0))
            veil.set_alpha(int(255 * min(1.0, alpha)))
            surface.blit(veil, (0, 0))

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            dt = clock.tick(60) / 1000.0
            for event in pygame.event.get():
                self.handle(event)
            self.update(dt)
            self.draw(self.screen)
            pygame.display.flip()
        for scene in self.stack:
            close = getattr(scene, "close", None)
            if close is not None:
                close()


class _SilentAudio:
    """Until the sounds are synthesized (loading screen)."""

    enabled = False

    def play(self, name: str) -> None:
        pass

    def music(self, kind) -> None:
        pass

    def update_volume(self) -> None:
        pass


def main(argv: Optional[List[str]] = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Space Pirate")
    parser.add_argument("level", nargs="?", help="direkt dieses Level spielen")
    parser.add_argument("--no-bot", action="store_true", help="den Bot nicht laden (ohne PyTorch schneller)")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    pygame.display.set_caption("Space Pirate")
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.SCALED | pygame.RESIZABLE)
    app = GameApp(screen, args.level, load_bot=not args.no_bot)
    if app.progress.settings.get("fullscreen"):
        app.set_fullscreen(True)
    app.run()
    pygame.quit()
