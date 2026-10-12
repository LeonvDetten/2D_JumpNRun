"""The screens of the game app: loading, main menu, level select, game, pause, result, settings, editor.

Every scene draws onto the fixed 1520 x 800 surface (the window scales it). Game logic runs at the game's
30 frames per second, the screens animate at the display rate.
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional

import pygame

from jumpnrun.app import gfx
from jumpnrun.app.gfx import CYAN, GOLD, MenuButton, glass_panel, level_thumbnail, shade
from jumpnrun.app.levels_index import RANDOM_TAB, TIER_NAMES, LevelEntry, random_entry
from jumpnrun.app.progress import HEAD_STARTS, decode_action, encode_action, format_time, stars_for
from jumpnrun.app.widgets import Chips, Slider, SmallButton, Tabs, Toggle
from jumpnrun.core.actions import Action
from jumpnrun.core.constants import FPS, SCREEN_H, SCREEN_W, TILE
from jumpnrun.core.sim import Simulation, Status
from jumpnrun.ui.widgets import ACCENT, GREEN, MUTED, RED, TEXT, YELLOW, font, text

STEP = 1.0 / FPS
NUM_TIERS = len(TIER_NAMES)
TIPS = [
    "Auf Gegner springen besiegt sie – und gibt einen kleinen Sprung nach oben.",
    "Enter schießt. Der Revolver braucht eine Sekunde zum Nachladen.",
    "Der Bot hat das Spiel per Reinforcement Learning gelernt – 50 Millionen Versuche lang.",
    "Drei Sterne gibt es, wenn du höchstens 15 % langsamer bist als der bewiesene Bot-Weg.",
    "Der Geist zeigt deinen besten Lauf – exakt, weil das Spiel deterministisch ist.",
    "Im Editor prüft „Prüfen“, ob der Bot dein Level schaffen kann.",
    "Zufallslevel kommen aus demselben Generator, mit dem der Bot trainiert hat.",
]


def keys_to_action(pressed) -> Action:
    """Same keys as game.py."""

    return Action(
        left=bool(pressed[pygame.K_a] or pressed[pygame.K_LEFT]),
        right=bool(pressed[pygame.K_d] or pressed[pygame.K_RIGHT]),
        jump=bool(pressed[pygame.K_w] or pressed[pygame.K_SPACE] or pressed[pygame.K_UP]),
        shoot=bool(pressed[pygame.K_RETURN]),
    )


def mouse_pos():
    return pygame.mouse.get_pos()


class Scene:
    overlay = False  # draw the scene below first (pause, result)
    music: Optional[str] = None

    def __init__(self, app):
        self.app = app

    def enter(self) -> None:
        pass

    def handle(self, event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        pass


def back_button() -> SmallButton:
    return SmallButton("back", "← Zurück", (30, 26, 150, 44))


def header(surface: pygame.Surface, title: str, subtitle: str = "") -> None:
    t = gfx.fancy_text(title, 40, (240, 248, 255), (120, 170, 240), (6, 10, 30), None, 3)
    surface.blit(t, t.get_rect(midtop=(SCREEN_W // 2, 2)))
    if subtitle:
        text(surface, subtitle, (SCREEN_W // 2, 78), 17, MUTED, False, "midtop")


# ===================================================================== loading
class LoadingScene(Scene):
    """Splash: logo, running pirate on the loading bar, tips. Loads one thing per frame."""

    MIN_SECONDS = 1.8

    def __init__(self, app, then=None):
        super().__init__(app)
        self.then = then
        self.t = 0.0
        self.steps = [
            ("Sprites laden", app.load_assets),
            ("Klänge synthetisieren", app.load_audio),
            ("Level einlesen", app.load_levels),
            ("Bot wecken", app.bot.start),
        ]
        self.done = 0
        self.tip = random.choice(TIPS)
        self.stars = [(random.uniform(0, SCREEN_W), random.uniform(0, SCREEN_H), random.uniform(0.3, 1.0))
                      for _ in range(160)]

    def update(self, dt: float) -> None:
        self.t += dt
        if self.done < len(self.steps):
            if self.t > 0.15 * (self.done + 1):  # let the first frames show before the heavy work
                self.steps[self.done][1]()
                self.done += 1
        elif self.t >= self.MIN_SECONDS and self.done == len(self.steps):
            self.done += 1  # switch once
            self.app.switch(self.then() if self.then else MenuScene(self.app))

    @property
    def fraction(self) -> float:
        work = min(1.0, self.done / len(self.steps))
        return min(work, self.t / self.MIN_SECONDS)

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.app.night_gradient(), (0, 0))
        for x, y, s in self.stars:
            glow = 0.5 + 0.5 * math.sin(self.t * 3 * s + x)
            c = int(90 + 150 * glow * s)
            pygame.draw.circle(surface, (c, c, min(255, c + 40)), (int((x - self.t * 40 * s) % SCREEN_W), int(y)), 1 + (s > 0.8))
        if self.app.logo is not None:
            self.app.logo.draw(surface, (SCREEN_W // 2, 330), self.t)
        else:
            t = font(80, True).render("SPACE PIRATE", True, GOLD)
            surface.blit(t, t.get_rect(center=(SCREEN_W // 2, 300)))
        bar = pygame.Rect(SCREEN_W // 2 - 360, 560, 720, 18)
        pygame.draw.rect(surface, (30, 34, 60), bar, border_radius=9)
        fill = bar.copy()
        fill.w = max(18, int(bar.w * self.fraction))
        pygame.draw.rect(surface, CYAN, fill, border_radius=9)
        pygame.draw.rect(surface, (120, 140, 200), bar, 2, border_radius=9)
        if self.app.assets is not None:
            frames = self.app.assets.player["RUN"][1]
            img = frames[int(self.t * 12) % len(frames)]
            surface.blit(img, img.get_rect(midbottom=(fill.right, bar.y + 2)))
        label = self.steps[min(self.done, len(self.steps) - 1)][0] + " …" if self.done < len(self.steps) else "Bereit!"
        text(surface, label, (SCREEN_W // 2, 596), 18, TEXT, True, "midtop")
        text(surface, "Tipp: " + self.tip, (SCREEN_W // 2, 720), 17, MUTED, False, "midtop")


# ===================================================================== main menu
class MenuScene(Scene):
    music = "menu"

    def __init__(self, app):
        super().__init__(app)
        a = app.assets
        icon = lambda img, h: pygame.transform.smoothscale(img, (int(img.get_width() * h / img.get_height()), h))  # noqa: E731
        bot_icon = icon(a.player["IDLE"][1][0], 46).copy()
        bot_icon.fill((90, 220, 255, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self.buttons = [
            MenuButton("single", "Einzelspieler", "Alle Level · Bestzeiten · Geist · Zufallslevel",
                       icon(a.player["IDLE"][1][0], 46)),
            MenuButton("bot", "Gegen den Bot", "Wettrennen gegen den KI-Piraten", bot_icon),
            MenuButton("editor", "Level-Editor", "Eigene Level bauen und prüfen", icon(a.block, 40)),
            MenuButton("settings", "Einstellungen", "Ton, Vollbild, Geist"),
            MenuButton("quit", "Beenden", ""),
        ]
        for i, b in enumerate(self.buttons):
            b.rect = pygame.Rect(110, 300 + i * 84, 470, 70)
        self.focus = 0
        self.t = 0.0
        self.demo = DemoPlayer(app)

    def enter(self) -> None:
        self.app.audio.music("menu")

    def _bot_state(self) -> None:
        b = self.buttons[1]
        bot = self.app.bot
        b.enabled = bot.ready
        if bot.loading:
            b.hint = "Der Bot lädt noch …"
        elif bot.error:
            b.hint = bot.error[:58]
        else:
            b.hint = "Wettrennen gegen den KI-Piraten"

    def activate(self, key: str) -> None:
        app = self.app
        app.audio.play("click")
        if key == "single":
            app.switch(LevelSelectScene(app, "single"))
        elif key == "bot":
            app.switch(LevelSelectScene(app, "bot"))
        elif key == "editor":
            app.switch(EditorScene(app))
        elif key == "settings":
            app.push(SettingsScene(app))
        elif key == "quit":
            app.quit()

    def handle(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_DOWN, pygame.K_s):
                self._move(1)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self._move(-1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                if self.buttons[self.focus].enabled:
                    self.activate(self.buttons[self.focus].key)
            elif event.key == pygame.K_ESCAPE:
                self.app.quit()
        elif event.type == pygame.MOUSEMOTION:
            for i, b in enumerate(self.buttons):
                if b.rect.collidepoint(event.pos) and i != self.focus:
                    self.focus = i
                    if b.enabled:
                        self.app.audio.play("hover")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for b in self.buttons:
                if b.enabled and b.rect.collidepoint(event.pos):
                    self.activate(b.key)

    def _move(self, d: int) -> None:
        for _ in range(len(self.buttons)):
            self.focus = (self.focus + d) % len(self.buttons)
            if self.buttons[self.focus].enabled:
                break
        self.app.audio.play("hover")

    def update(self, dt: float) -> None:
        self.t += dt
        self.app.background.update(dt)
        self._bot_state()
        for i, b in enumerate(self.buttons):
            b.update(dt, i == self.focus)
        self.demo.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        self.app.background.draw(surface)
        self.app.logo.draw(surface, (SCREEN_W // 2, 170), self.t, 0.9)
        for b in self.buttons:
            b.draw(surface)
        panel = pygame.Rect(680, 300, 740, 400)
        glass_panel(surface, panel.inflate(16, 50).move(0, -17), 200, CYAN)
        text(surface, "Demo: der Bot spielt „" + self.demo.title + "“", (panel.x, panel.y - 36), 17, CYAN, True)
        self.demo.draw(surface, panel)
        done, total_stars = self.app.progress_summary()
        text(surface, f"{done} Level geschafft  ·  {total_stars} Sterne", (110, 730), 18, GOLD, True)
        text(surface, "↑ ↓ + Enter oder Maus  ·  F11 Vollbild", (SCREEN_W - 40, 760), 15, MUTED, False, "topright")


class DemoPlayer:
    """Replays a stored proven bot solution in a small window (loops)."""

    LEVELS = ("berg", "festung", "parcours")

    def __init__(self, app):
        from jumpnrun.editor.model import load_solution
        from jumpnrun.render.renderer import Renderer

        self.app = app
        self.renderer = Renderer()
        self.surface = pygame.Surface((SCREEN_W, SCREEN_H))
        self.items = []
        for e in app.tabs.get("Test-Serie", []):
            if e.path is not None and e.path.stem in self.LEVELS:
                actions = load_solution(e.path)
                if actions:
                    self.items.append((e, actions))
        self.index = -1
        self.title = ""
        self.sim = None
        self.acc = 0.0
        self.end = 0
        self._next()

    def _next(self) -> None:
        if not self.items:
            return
        self.index = (self.index + 1) % len(self.items)
        entry, self.actions = self.items[self.index]
        self.title = entry.title
        self.sim = Simulation(entry.level())
        self.frame = 0
        self.end = 0

    def update(self, dt: float) -> None:
        if self.sim is None:
            return
        self.acc += dt
        while self.acc >= STEP:
            self.acc -= STEP
            if self.sim.status != Status.RUNNING or self.frame // 2 >= len(self.actions):
                self.end += 1
                if self.end > 45:
                    self._next()
                continue
            from jumpnrun.core.actions import BOT_ACTIONS_V3

            self.sim.step(BOT_ACTIONS_V3[self.actions[self.frame // 2]])
            self.frame += 1

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        if self.sim is None:
            return
        from jumpnrun.render.renderer import camera_x

        r = self.renderer
        cam = camera_x(self.sim.level, self.sim.player.x)
        r.draw_level(self.surface, self.sim.level, cam)
        r.draw_chests(self.surface, self.sim.level, cam, self.end if self.sim.status == Status.WON else 0)
        r.draw_sim_objects(self.surface, self.sim, cam)
        r.draw_player(self.surface, self.sim.player, self.sim.frame, cam)
        surface.blit(pygame.transform.smoothscale(self.surface, rect.size), rect)
        pygame.draw.rect(surface, (120, 150, 220), rect, 2, border_radius=6)


# ===================================================================== level select
class LevelSelectScene(Scene):
    music = "menu"
    CARD_W, CARD_H = 296, 196
    GRID_X, GRID_Y = 34, 168
    COLS = 3

    def __init__(self, app, mode: str, tab: Optional[str] = None):
        super().__init__(app)
        self.mode = mode  # "single" | "bot"
        app.refresh_own_levels()
        labels = [name for name in app.tabs] + [RANDOM_TAB]
        self.tabs = Tabs(labels, (34, 104))
        if tab in labels:
            self.tabs.index = labels.index(tab)
        self.back = back_button()
        self.start = MenuButton("go", "Los!" if mode == "single" else "Rennen starten!", "")
        self.start.rect = pygame.Rect(1046, 694, 420, 66)
        self.selected = 0
        self.scroll = 0
        self.thumbs: Dict[str, pygame.Surface] = {}
        self.head = Chips((1066, 556), HEAD_STARTS, [f"{s} s" for s in HEAD_STARTS], app.progress.settings["head_start"])
        self.tier = app.random_tier
        self.seed = app.random_seed
        self.tier_slider = Slider((1066, 420, 340, 10), self.tier / (NUM_TIERS - 1), show_percent=False)
        self.dice = SmallButton("dice", "Neu würfeln", (1066, 470, 180, 44))
        self.random: Optional[LevelEntry] = None
        self.t = 0.0
        self._make_random()

    def enter(self) -> None:
        self.app.audio.music("menu")

    # ---------------------------------------------------------------- data
    @property
    def entries(self) -> List[LevelEntry]:
        return self.app.tabs.get(self.tabs.current, [])

    @property
    def is_random(self) -> bool:
        return self.tabs.current == RANDOM_TAB

    @property
    def entry(self) -> Optional[LevelEntry]:
        if self.is_random:
            return self.random
        entries = self.entries
        return entries[self.selected] if entries and 0 <= self.selected < len(entries) else None

    def _make_random(self) -> None:
        self.random = random_entry(self.tier, self.seed)
        self.app.random_tier, self.app.random_seed = self.tier, self.seed

    def thumb(self, entry: LevelEntry, size) -> pygame.Surface:
        key = f"{entry.key}:{size}"
        if key not in self.thumbs:
            self.thumbs[key] = level_thumbnail(entry.level(), size)
        return self.thumbs[key]

    def card_rect(self, i: int) -> pygame.Rect:
        row, col = divmod(i, self.COLS)
        return pygame.Rect(self.GRID_X + col * (self.CARD_W + 16), self.GRID_Y + (row - self.scroll) * (self.CARD_H + 16),
                           self.CARD_W, self.CARD_H)

    # ---------------------------------------------------------------- input
    def go(self) -> None:
        entry = self.entry
        if entry is None:
            return
        self.app.audio.play("click")
        self.app.progress.settings["head_start"] = self.head.value
        self.app.progress.save()
        self.app.switch(GameScene(self.app, entry, self.mode, self.head.value if self.mode == "bot" else 0, self.tabs.current))

    def handle(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            k = event.key
            if k == pygame.K_ESCAPE:
                self.app.switch(MenuScene(self.app))
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.go()
            elif k in (pygame.K_TAB, pygame.K_q, pygame.K_e):
                d = -1 if k == pygame.K_q or (event.mod & pygame.KMOD_SHIFT) else 1
                self.tabs.index = (self.tabs.index + d) % len(self.tabs.labels)
                self.selected, self.scroll = 0, 0
                self.app.audio.play("hover")
            elif self.is_random:
                if k in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                    self.tier = max(0, min(NUM_TIERS - 1, self.tier + (1 if k in (pygame.K_RIGHT, pygame.K_d) else -1)))
                    self.tier_slider.value = self.tier / (NUM_TIERS - 1)
                    self._make_random()
                elif k == pygame.K_r:
                    self.seed = random.randint(1, 99999)
                    self._make_random()
            else:
                moves = {pygame.K_LEFT: -1, pygame.K_a: -1, pygame.K_RIGHT: 1, pygame.K_d: 1,
                         pygame.K_UP: -self.COLS, pygame.K_w: -self.COLS, pygame.K_DOWN: self.COLS, pygame.K_s: self.COLS}
                if k in moves and self.entries:
                    self.selected = max(0, min(len(self.entries) - 1, self.selected + moves[k]))
                    self._keep_visible()
                    self.app.audio.play("hover")
        elif event.type == pygame.MOUSEWHEEL and not self.is_random:
            rows = -(-len(self.entries) // self.COLS)
            self.scroll = max(0, min(max(0, rows - 3), self.scroll - event.y))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.back.hit(pos):
                self.app.audio.play("click")
                self.app.switch(MenuScene(self.app))
            elif self.tabs.handle_click(pos):
                self.selected, self.scroll = 0, 0
                self.app.audio.play("click")
            elif self.start.rect.collidepoint(pos):
                self.go()
            elif self.mode == "bot" and self.head.handle_click(pos):
                self.app.audio.play("click")
            elif self.is_random and self.dice.hit(pos):
                self.seed = random.randint(1, 99999)
                self._make_random()
                self.app.audio.play("click")
            elif self.is_random:
                for box, tier in getattr(self, "_tier_boxes", []):
                    if box.collidepoint(pos) and tier != self.tier:
                        self.tier = tier
                        self.tier_slider.value = tier / (NUM_TIERS - 1)
                        self._make_random()
                        self.app.audio.play("hover")
            else:
                for i in range(len(self.entries)):
                    if self.card_rect(i).collidepoint(pos) and pos[1] > self.GRID_Y - 4:
                        if i == self.selected and getattr(event, "clicks", 1) >= 2:
                            self.go()
                        self.selected = i
                        self.app.audio.play("hover")
        if self.is_random and self.tier_slider.handle(event):
            tier = int(round(self.tier_slider.value * (NUM_TIERS - 1)))
            if tier != self.tier:
                self.tier = tier
                self._make_random()

    def _keep_visible(self) -> None:
        row = self.selected // self.COLS
        if row < self.scroll:
            self.scroll = row
        elif row >= self.scroll + 3:
            self.scroll = row - 2

    def update(self, dt: float) -> None:
        self.t += dt
        self.app.background.update(dt)
        self.start.update(dt, True)  # the main call to action always glows

    # ---------------------------------------------------------------- draw
    def draw(self, surface: pygame.Surface) -> None:
        self.app.background.draw(surface)
        mouse = mouse_pos()
        title = "Einzelspieler" if self.mode == "single" else "Rennen gegen den Bot"
        header(surface, title, "Level wählen")
        self.back.draw(surface, mouse)
        self.tabs.draw(surface, mouse)
        if self.is_random:
            self._draw_random(surface)
        else:
            self._draw_grid(surface, mouse)
        self._draw_detail(surface)

    def _draw_grid(self, surface: pygame.Surface, mouse) -> None:
        entries = self.entries
        clip = pygame.Rect(0, self.GRID_Y - 6, 1000, SCREEN_H - self.GRID_Y)
        surface.set_clip(clip)
        if not entries:
            msg = "Noch keine eigenen Level – im Level-Editor bauen und unter levels/eigene/ speichern."
            text(surface, msg, (self.GRID_X + 10, self.GRID_Y + 20), 18, MUTED)
        progress = self.app.progress
        for i, e in enumerate(entries):
            r = self.card_rect(i)
            if r.bottom < clip.y or r.y > clip.bottom:
                continue
            sel = i == self.selected
            glass_panel(surface, r, 220 if sel else 170, GOLD if sel else ((110, 130, 190) if r.collidepoint(mouse) else None), 14)
            surface.blit(self.thumb(e, (r.w - 20, 100)), (r.x + 10, r.y + 10))
            text(surface, e.title, (r.x + 14, r.y + 118), 19, TEXT, True)
            best = progress.best_frames(e.key)
            text(surface, f"Bestzeit {format_time(best)}" if best else "noch nicht geschafft", (r.x + 14, r.y + 146), 15,
                 GREEN if best else MUTED)
            text(surface, f"{'Bot' if e.par_proven else 'Richtzeit'} {format_time(e.par_frames)}", (r.right - 14, r.y + 146),
                 15, CYAN if e.par_proven else MUTED, False, "topright")
            gfx.stars(surface, (r.x + 50, r.y + 178), progress.stars(e.key), 9)
            if progress.get(e.key).get("race_wins"):
                text(surface, f"{progress.get(e.key)['race_wins']}× Bot besiegt", (r.right - 14, r.y + 170), 14, GOLD,
                     True, "topright")
        surface.set_clip(None)
        rows = -(-len(entries) // self.COLS)
        if rows > 3:
            track = pygame.Rect(1004, self.GRID_Y, 6, 3 * (self.CARD_H + 16) - 16)
            pygame.draw.rect(surface, (40, 46, 70), track, border_radius=3)
            h = track.h * 3 // rows
            y = track.y + (track.h - h) * self.scroll // max(1, rows - 3)
            pygame.draw.rect(surface, CYAN, (track.x, y, 6, h), border_radius=3)

    def _draw_random(self, surface: pygame.Surface) -> None:
        r = pygame.Rect(34, 168, 970, 600)
        glass_panel(surface, r, 180, None, 18)
        text(surface, "Zufallslevel", (r.x + 30, r.y + 24), 30, TEXT, True)
        text(surface, "Aus dem Generator, mit dem der Bot trainiert hat – jedes Level ist lösbar gebaut.",
             (r.x + 30, r.y + 68), 17, MUTED)
        y = r.y + 120
        for tier in range(NUM_TIERS):
            col, row = divmod(tier, 7)
            box = pygame.Rect(r.x + 30 + col * 470, y + row * 60, 450, 50)
            active = tier == self.tier
            glass_panel(surface, box, 230 if active else 120, GOLD if active else None, 12)
            text(surface, f"{tier}", (box.x + 18, box.centery), 22, GOLD if active else MUTED, True, "midleft")
            text(surface, TIER_NAMES[tier], (box.x + 60, box.centery), 19, TEXT if active else MUTED, True, "midleft")
        self._tier_boxes = [(pygame.Rect(r.x + 30 + (t // 7) * 470, y + (t % 7) * 60, 450, 50), t) for t in range(NUM_TIERS)]
        text(surface, "← → Stufe · R neu würfeln", (r.x + 30, r.bottom - 34), 15, MUTED)

    def _draw_detail(self, surface: pygame.Surface) -> None:
        r = pygame.Rect(1030, 168, 470, 610)
        glass_panel(surface, r, 210, CYAN, 18)
        e = self.entry
        if e is None:
            text(surface, "Kein Level ausgewählt", r.center, 20, MUTED, True, "center")
            return
        surface.blit(self.thumb(e, (r.w - 32, 150)), (r.x + 16, r.y + 16))
        text(surface, e.title, (r.x + 22, r.y + 180), 26, TEXT, True)
        text(surface, e.subtitle, (r.x + 22, r.y + 216), 15, MUTED)
        progress = self.app.progress
        best = progress.best_frames(e.key)
        y = r.y + 250
        if self.is_random:
            text(surface, "Stufe", (r.x + 36, y), 17, MUTED)
            text(surface, f"{self.tier} – {TIER_NAMES[self.tier]}", (r.x + 120, y), 17, TEXT, True)
            self.tier_slider.rect.topleft = (r.x + 36, y + 34)
            self.tier_slider.draw(surface)
            self.dice.rect.topleft = (r.x + 36, y + 62)
            self.dice.draw(surface, mouse_pos())
            text(surface, f"Seed {self.seed}", (self.dice.rect.right + 16, self.dice.rect.centery), 16, MUTED, False,
                 "midleft")
            y += 124
        rows = [("Länge", f"{e.level().goal_x // TILE + 1} Spalten"), (e.par_label, format_time(e.par_frames)),
                ("Bestzeit", format_time(best) if best else "–")]
        if self.mode == "single":
            rows.append(("Geist", "dein Bestlauf läuft mit" if progress.ghost(e.key) and progress.settings["ghost"]
                         else ("aus (Einstellungen)" if not progress.settings["ghost"] else "nach dem ersten Sieg")))
        for label, value in rows:
            text(surface, label, (r.x + 36, y), 17, MUTED)
            text(surface, value, (r.x + 170, y), 17, TEXT, True)
            y += 30
        if not self.is_random:
            gfx.stars(surface, (r.x + 110, y + 18), progress.stars(e.key), 16)
        if self.mode == "bot":
            text(surface, "Dein Vorsprung:", (r.x + 36, 528), 17, MUTED)
            self.head.draw(surface)
            races = progress.get(e.key)
            if races.get("races"):
                text(surface, f"Gegen den Bot: {races.get('race_wins', 0)} von {races['races']} Rennen gewonnen",
                     (r.x + 36, 610), 15, GOLD)
        self.start.draw(surface)


# ===================================================================== game
class GameScene(Scene):
    """One run. Single player: time trial with ghost. Bot mode: race, deaths send you back to the start."""

    music = "game"
    COUNTDOWN = 3 * FPS

    def __init__(self, app, entry: LevelEntry, mode: str = "single", head_start: int = 0, tab: str = ""):
        super().__init__(app)
        from jumpnrun.render.renderer import Renderer

        self.entry, self.mode, self.head_start, self.tab = entry, mode, head_start, tab
        self.level = entry.level()
        self.renderer = Renderer()
        self.view = pygame.Surface((SCREEN_W, SCREEN_H))
        self.ghost_inputs = app.progress.ghost(entry.key) if mode == "single" and app.progress.settings["ghost"] else None
        self.best = app.progress.best_frames(entry.key)
        self.reset()

    def enter(self) -> None:
        self.app.audio.music("game")

    def reset(self) -> None:
        self.sim = Simulation(self.level)
        self.ghost = Simulation(self.level) if self.ghost_inputs else None
        self.bot = None
        if self.mode == "bot" and self.app.bot.ready:
            from jumpnrun.app.bot import BotRacer

            self.bot = BotRacer(self.app.bot.model, self.level, delay_frames=self.head_start * FPS)
        self.countdown = self.COUNTDOWN
        self.race_frame = 0
        self.inputs: List[int] = []
        self.acc = 0.0
        self.respawn = 0
        self.deaths = 0
        self.finished = False
        self.after_end = 0
        self.dead_reason: Optional[str] = None
        self.banner = ("", 0)
        self.result_shown = False

    # ---------------------------------------------------------------- input
    def handle(self, event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if self.dead_reason is not None:
            if event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                self.reset()
            elif event.key == pygame.K_ESCAPE:
                self.app.switch(LevelSelectScene(self.app, self.mode, self.tab))
            return
        if event.key in (pygame.K_ESCAPE, pygame.K_p) and not self.finished:
            self.app.audio.play("click")
            self.app.push(PauseScene(self.app, self))
        elif event.key == pygame.K_r and not self.finished:
            self.reset()

    # ---------------------------------------------------------------- logic
    def update(self, dt: float) -> None:
        self.acc += min(dt, 0.1)
        while self.acc >= STEP:
            self.acc -= STEP
            self.tick()

    def tick(self) -> None:
        audio = self.app.audio
        if self.countdown > 0:
            if self.countdown % FPS == 0:
                audio.play("beep")
            self.countdown -= 1
            if self.countdown == 0:
                audio.play("go")
            return
        if self.dead_reason is not None:
            return
        if self.finished:
            self.after_end += 1
            if self.bot is not None:
                self.bot.step()
            if self.after_end == 45 and not self.result_shown:
                self.result_shown = True
                self.app.push(ResultScene(self.app, self))
            return
        self.race_frame += 1
        sim = self.sim
        if self.respawn > 0:  # bot mode: back to the start after a death
            self.respawn -= 1
            if self.respawn == 0:
                self.sim = sim = Simulation(self.level)
        else:
            action = keys_to_action(pygame.key.get_pressed())
            self.inputs.append(encode_action(action))
            before = (sim.jumps, sim.kills_stomp, sim.kills_shot, sim.player.shoot_cooldown)
            sim.step(action)
            if sim.jumps > before[0]:
                audio.play("jump")
            if sim.kills_stomp > before[1]:
                audio.play("stomp")
            if sim.kills_shot > before[2]:
                audio.play("hit")
            if sim.player.shoot_cooldown > before[3]:
                audio.play("shoot")
        if self.ghost is not None:
            i = self.race_frame - 1
            if i < len(self.ghost_inputs) and self.ghost.status == Status.RUNNING:
                self.ghost.step(decode_action(self.ghost_inputs[i]))
        if self.bot is not None:
            event = self.bot.step()
            if event == "won" and not self.finished:
                self.banner = ("Der Bot ist im Ziel!", 60)
            if self.bot.won and self.race_frame - self.bot.finish_frame >= 2 * FPS and sim.status != Status.WON:
                audio.play("lose")  # the race is decided
                self.finished = True
                self.after_end = 0
                return
        if self.banner[1] > 0:
            self.banner = (self.banner[0], self.banner[1] - 1)
        if sim.status == Status.WON:
            audio.play("chest")
            audio.play("win" if self.won else "lose")
            self.finished = True
            self.after_end = 0
        elif sim.status in (Status.DIED_PIT, Status.DIED_ENEMY) and self.respawn == 0:
            audio.play("death")
            self.deaths += 1
            if self.mode == "bot":
                self.respawn = FPS
                self.banner = ("Autsch – zurück zum Start!", 40)
            else:
                self.dead_reason = "Du bist in eine Grube gefallen." if sim.status == Status.DIED_PIT \
                    else "Ein Gegner hat dich erwischt."

    @property
    def won(self) -> bool:
        if self.sim.status != Status.WON:
            return False
        return self.bot is None or not self.bot.won or self.bot.finish_frame >= self.race_frame

    # ---------------------------------------------------------------- draw
    def draw(self, surface: pygame.Surface) -> None:
        from jumpnrun.render.renderer import camera_x, player_sprite

        r = self.renderer
        sim = self.sim
        cam = camera_x(self.level, sim.player.x)
        r.draw_level(surface, self.level, cam)
        r.draw_chests(surface, self.level, cam, self.after_end if sim.status == Status.WON else 0)
        if self.ghost is not None and self.ghost.status != Status.DIED_PIT:
            img = player_sprite(self.ghost.player, self.ghost.frame).copy()
            img.fill((200, 220, 255, 110), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(img, (self.ghost.player.x - cam, self.ghost.player.y))
        if self.bot is not None:
            self._draw_bot(surface, cam)
        r.draw_sim_objects(surface, sim, cam)
        if self.respawn == 0:
            r.draw_player(surface, sim.player, sim.frame, cam)
        self._draw_hud(surface)
        if self.countdown > 0:
            n = self.countdown // FPS + 1
            k = (self.countdown % FPS) / FPS
            t = gfx.fancy_text(str(n), int(150 + 60 * k), glow_color=(255, 170, 60))
            t.set_alpha(int(255 * min(1.0, k * 2 + 0.3)))
            surface.blit(t, t.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 20)))
            if self.mode == "bot" and self.head_start:
                text(surface, f"Du startest {self.head_start} s vor dem Bot", (SCREEN_W // 2, SCREEN_H // 2 + 100), 22,
                     CYAN, True, "center")
        elif self.race_frame < 20:
            t = gfx.fancy_text("LOS!", 150, glow_color=(255, 170, 60))
            t.set_alpha(int(255 * (1 - self.race_frame / 20)))
            surface.blit(t, t.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 20)))
        if self.banner[1] > 0:
            b = font(26, True).render(self.banner[0], True, YELLOW)
            box = b.get_rect(center=(SCREEN_W // 2, 170)).inflate(40, 20)
            glass_panel(surface, box, 220, YELLOW, 14)
            surface.blit(b, b.get_rect(center=box.center))
        if self.dead_reason is not None:
            shade(surface, 140)
            box = pygame.Rect(0, 0, 640, 250)
            box.center = (SCREEN_W // 2, SCREEN_H // 2)
            glass_panel(surface, box, 235, RED, 20)
            t = gfx.fancy_text("Autsch!", 64, (255, 200, 200), (190, 40, 40), (40, 6, 6))
            surface.blit(t, t.get_rect(midtop=(box.centerx, box.y)))
            text(surface, self.dead_reason, (box.centerx, box.y + 120), 22, TEXT, True, "midtop")
            text(surface, "R / Enter = nochmal   ·   Esc = Levelauswahl", (box.centerx, box.y + 180), 18, MUTED, False,
                 "midtop")

    def _draw_bot(self, surface: pygame.Surface, cam: int) -> None:
        from jumpnrun.render.renderer import player_sprite

        bot = self.bot
        p = bot.sim.player
        if not bot.visible and not bot.won:
            return
        img = player_sprite(p, bot.sim.frame).copy()
        img.fill((110, 230, 255, 150), special_flags=pygame.BLEND_RGBA_MULT)
        x = p.x - cam
        if -40 < x < SCREEN_W:
            surface.blit(img, (x, p.y))
            text(surface, "BOT", (x + 20, p.y - 6), 14, CYAN, True, "midbottom")
            return
        tiles = (p.x - self.sim.player.x) // TILE
        y = max(150, min(SCREEN_H - 60, p.y + 30))
        if x >= SCREEN_W:
            pts = [(SCREEN_W - 8, y), (SCREEN_W - 30, y - 16), (SCREEN_W - 30, y + 16)]
            label_pos, anchor = (SCREEN_W - 38, y), "midright"
        else:
            pts = [(8, y), (30, y - 16), (30, y + 16)]
            label_pos, anchor = (38, y), "midleft"
        pygame.draw.polygon(surface, CYAN, pts)
        text(surface, f"BOT {tiles:+d}", label_pos, 18, CYAN, True, anchor)

    def _draw_hud(self, surface: pygame.Surface) -> None:
        bar = pygame.Rect(16, 12, SCREEN_W - 32, 64)
        glass_panel(surface, bar, 190, None, 16)
        frames = self.race_frame if self.mode == "bot" else self.sim.frame
        text(surface, format_time(frames), (bar.x + 22, bar.centery), 34, TEXT, True, "midleft")
        par = self.entry.par_frames
        # progress bar from start to the chest
        track = pygame.Rect(bar.x + 250, bar.centery - 4, 760, 8)
        pygame.draw.rect(surface, (50, 56, 84), track, border_radius=4)
        x0, x1 = self.level.spawn[0], max(self.level.goal_x, self.level.spawn[0] + 1)

        def mark(px, color, r, label=None):
            k = max(0.0, min(1.0, (px - x0) / (x1 - x0)))
            x = track.x + int(track.w * k)
            pygame.draw.circle(surface, color, (x, track.centery), r)
            if label:
                text(surface, label, (x, track.y - 6), 12, color, True, "midbottom")

        star_x = track.right
        gfx.star(surface, (star_x + 2, track.centery), 11, GOLD)
        if self.ghost is not None:
            mark(self.ghost.player.x, (200, 210, 240), 6, "Geist")
        if self.bot is not None:
            mark(self.bot.sim.player.x if self.bot.visible or self.bot.won else x0, CYAN, 7, "Bot")
        mark(self.sim.player.x, GREEN, 8)
        right = bar.right - 22
        if self.mode == "bot":
            bot = self.bot
            if bot is None:
                status = "Bot nicht geladen"
            elif bot.won:
                status = f"Bot im Ziel: {format_time(bot.finish_frame)}"
            elif bot.wait > 0:
                status = f"Bot startet in {bot.wait / FPS:.1f} s"
            elif bot.respawn:
                status = "Bot: zurück zum Start"
            else:
                status = f"Bot unterwegs · {bot.deaths}× gestorben"
            text(surface, status, (right, bar.centery), 19, CYAN, True, "midright")
        else:
            limits = [("3★", int(par * 1.15)), ("2★", int(par * 1.5))] if par else []
            best = f"Best {format_time(self.best)}" if self.best else "Noch keine Bestzeit"
            text(surface, best, (right, bar.y + 10), 17, GOLD if self.best else MUTED, True, "topright")
            if limits:
                goal = "   ".join(f"{s} ≤ {format_time(f)}" for s, f in limits)
                ok = frames <= limits[0][1]
                text(surface, goal, (right, bar.y + 36), 15, GREEN if ok else MUTED, False, "topright")


# ===================================================================== pause
class PauseScene(Scene):
    overlay = True

    def __init__(self, app, game: GameScene):
        super().__init__(app)
        self.game = game
        labels = [("resume", "Weiter"), ("restart", "Neustart"), ("settings", "Einstellungen"),
                  ("select", "Levelauswahl"), ("menu", "Hauptmenü")]
        self.buttons = [MenuButton(k, label) for k, label in labels]
        for i, b in enumerate(self.buttons):
            b.rect = pygame.Rect(SCREEN_W // 2 - 210, 250 + i * 78, 420, 64)
        self.focus = 0

    def activate(self, key: str) -> None:
        app = self.app
        app.audio.play("click")
        if key == "resume":
            app.pop()
        elif key == "restart":
            app.pop()
            self.game.reset()
        elif key == "settings":
            app.push(SettingsScene(app))
        elif key == "select":
            app.switch(LevelSelectScene(app, self.game.mode, self.game.tab))
        elif key == "menu":
            app.switch(MenuScene(app))

    def handle(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                self.activate("resume")
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.focus = (self.focus + 1) % len(self.buttons)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.focus = (self.focus - 1) % len(self.buttons)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.activate(self.buttons[self.focus].key)
        elif event.type == pygame.MOUSEMOTION:
            for i, b in enumerate(self.buttons):
                if b.rect.collidepoint(event.pos):
                    self.focus = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for b in self.buttons:
                if b.rect.collidepoint(event.pos):
                    self.activate(b.key)

    def update(self, dt: float) -> None:
        for i, b in enumerate(self.buttons):
            b.update(dt, i == self.focus)

    def draw(self, surface: pygame.Surface) -> None:
        shade(surface, 160)
        t = gfx.fancy_text("Pause", 72, glow_color=(255, 170, 60))
        surface.blit(t, t.get_rect(midtop=(SCREEN_W // 2, 110)))
        for b in self.buttons:
            b.draw(surface)


# ===================================================================== result
class ResultScene(Scene):
    overlay = True

    def __init__(self, app, game: GameScene):
        super().__init__(app)
        self.game = game
        self.t = 0.0
        entry = game.entry
        progress = app.progress
        self.won = game.won
        self.frames = game.race_frame if game.mode == "bot" else game.sim.frame
        self.info = {}
        if game.mode == "single":
            self.info = progress.record_win(entry.key, self.frames, game.inputs, entry.par_frames)
            self.stars = self.info["stars"]
        else:
            self.info = progress.record_race(entry.key, self.won, self.frames)
            self.stars = stars_for(self.frames, entry.par_frames) if self.won else 0
        self.confetti = gfx.Confetti() if self.won else None
        self.shown_stars = 0
        labels = [("again", "Nochmal"), ("next", "Nächstes Level"), ("select", "Levelauswahl")]
        self.buttons = [SmallButton(k, label, accent=(k == "next" and self.won) or (k == "again" and not self.won))
                        for k, label in labels]
        x = SCREEN_W // 2 - 300
        for b in self.buttons:
            b.rect = pygame.Rect(x, 566, 190, 52)
            x += 205
        self.app.audio.music(None)

    def next_entry(self) -> Optional[LevelEntry]:
        e = self.game.entry
        if e.tier is not None:
            seed = random.randint(1, 99999)
            self.app.random_seed = seed
            return random_entry(e.tier, seed)
        entries = self.app.tabs.get(self.game.tab, [])
        keys = [x.key for x in entries]
        if e.key in keys and keys.index(e.key) + 1 < len(entries):
            return entries[keys.index(e.key) + 1]
        return None

    def activate(self, key: str) -> None:
        app, g = self.app, self.game
        app.audio.play("click")
        if key == "again":
            app.switch(GameScene(app, g.entry, g.mode, g.head_start, g.tab))
        elif key == "next":
            nxt = self.next_entry()
            if nxt is None:
                app.switch(LevelSelectScene(app, g.mode, g.tab))
            else:
                app.switch(GameScene(app, nxt, g.mode, g.head_start, g.tab))
        elif key == "select":
            app.switch(LevelSelectScene(app, g.mode, g.tab))

    def handle(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.activate("next" if self.won else "again")
            elif event.key == pygame.K_r:
                self.activate("again")
            elif event.key == pygame.K_n:
                self.activate("next")
            elif event.key == pygame.K_ESCAPE:
                self.activate("select")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for b in self.buttons:
                if b.hit(event.pos):
                    self.activate(b.key)

    def update(self, dt: float) -> None:
        self.t += dt
        if self.confetti:
            self.confetti.update(dt)
        due = int((self.t - 0.5) / 0.35) + 1 if self.t > 0.5 else 0
        while self.shown_stars < min(due, self.stars):
            self.shown_stars += 1
            self.app.audio.play("star")
        self.game.update(dt)  # the bot keeps running in the background

    def draw(self, surface: pygame.Surface) -> None:
        shade(surface, 150)
        if self.confetti:
            self.confetti.draw(surface)
        g = self.game
        box = pygame.Rect(0, 0, 720, 520)
        box.center = (SCREEN_W // 2, SCREEN_H // 2 + 10)
        glass_panel(surface, box, 235, GOLD if self.won else RED, 22)
        if g.mode == "bot":
            title = "Bot geschlagen!" if self.won else "Der Bot war schneller"
        else:
            title = "Geschafft!"
        t = gfx.fancy_text(title, 60, glow_color=(255, 170, 60) if self.won else None) if self.won else \
            gfx.fancy_text(title, 54, (255, 210, 210), (190, 60, 60), (40, 6, 6))
        surface.blit(t, t.get_rect(midtop=(box.centerx, box.y - 4)))
        text(surface, g.entry.title, (box.centerx, box.y + 96), 20, MUTED, True, "midtop")
        finished = g.sim.status == Status.WON
        text(surface, format_time(self.frames) if finished else "nicht im Ziel", (box.centerx, box.y + 130),
             64 if finished else 46, TEXT if finished else MUTED, True, "midtop")
        cx, cy = box.centerx, box.y + 250
        for i in range(3):
            filled = i < self.shown_stars
            pop = 1.0
            if filled and i == self.shown_stars - 1:
                pop = 1.0 + 0.4 * max(0.0, 1 - ((self.t - 0.5) % 0.35) / 0.2)
            gfx.star(surface, (cx + (i - 1) * 90, cy), 34 * pop, GOLD if filled else (60, 66, 92))
        y = box.y + 310
        lines = []
        if g.mode == "single":
            old = self.info.get("old_best")
            if self.info.get("best"):
                lines.append(("Neue Bestzeit!" + (f"  (vorher {format_time(old)})" if old else ""), GOLD))
            else:
                lines.append((f"Bestzeit bleibt {format_time(old)}", MUTED))
            lines.append((f"{g.entry.par_label}: {format_time(g.entry.par_frames)}  ·  "
                          f"3★ bis {format_time(int(g.entry.par_frames * 1.15))}", CYAN))
        else:
            bot = g.bot
            if bot is not None and bot.won and not finished:
                left = max(0, (g.level.goal_x - g.sim.player.x) // TILE)
                lines.append((f"Bot im Ziel nach {format_time(bot.finish_frame)} – dir fehlten noch {left} Spalten", CYAN))
            elif bot is not None and bot.won:
                diff = (self.frames - bot.finish_frame) / FPS
                lines.append((f"Bot: {format_time(bot.finish_frame)}   ({'+' if diff >= 0 else '−'}{abs(diff):.2f} s)",
                              CYAN))
            elif bot is not None:
                lines.append(("Der Bot war noch unterwegs.", CYAN))
            lines.append((f"Vorsprung {g.head_start} s · {g.deaths}× gestorben · "
                          f"{self.info.get('wins', 0)} von {self.info.get('races', 1)} Rennen gewonnen", MUTED))
        for msg, color in lines:
            text(surface, msg, (box.centerx, y), 20, color, True, "midtop")
            y += 34
        mouse = mouse_pos()
        for b in self.buttons:
            b.draw(surface, mouse)
        text(surface, "Enter = " + ("nächstes Level" if self.won else "nochmal") + "  ·  R nochmal  ·  Esc Levelauswahl",
             (box.centerx, box.bottom - 26), 15, MUTED, False, "midtop")


# ===================================================================== settings
class SettingsScene(Scene):
    overlay = True

    def __init__(self, app):
        super().__init__(app)
        s = app.progress.settings
        self.box = pygame.Rect(0, 0, 820, 600)
        self.box.center = (SCREEN_W // 2, SCREEN_H // 2)
        x = self.box.x + 330
        y = self.box.y + 110
        self.fullscreen = Toggle((x, y, 64, 32), s["fullscreen"])
        self.music = Slider((x, y + 70, 300, 10), s["music"])
        self.sfx = Slider((x, y + 130, 300, 10), s["sfx"])
        self.ghost = Toggle((x, y + 180, 64, 32), s["ghost"])
        self.head = Chips((x, y + 240), HEAD_STARTS, [f"{v} s" for v in HEAD_STARTS], s["head_start"])
        self.done = SmallButton("done", "Fertig", (self.box.right - 200, self.box.bottom - 70, 170, 50), accent=True)

    def close(self) -> None:
        s = self.app.progress.settings
        s.update(fullscreen=self.fullscreen.value, music=round(self.music.value, 2), sfx=round(self.sfx.value, 2),
                 ghost=self.ghost.value, head_start=self.head.value)
        self.app.progress.save()
        self.app.pop()

    def handle(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.close()
            return
        for slider in (self.music, self.sfx):
            if slider.handle(event):
                self.app.progress.settings["music"] = self.music.value
                self.app.progress.settings["sfx"] = self.sfx.value
                self.app.audio.update_volume()
                if slider is self.sfx and event.type == pygame.MOUSEBUTTONUP:
                    self.app.audio.play("jump")
                return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.fullscreen.handle_click(event.pos):
                self.app.set_fullscreen(self.fullscreen.value)
            elif self.ghost.handle_click(event.pos) or self.head.handle_click(event.pos):
                self.app.audio.play("click")
            elif self.done.hit(event.pos):
                self.close()

    def draw(self, surface: pygame.Surface) -> None:
        shade(surface, 215)
        b = self.box
        glass_panel(surface, b, 240, CYAN, 22)
        text(surface, "Einstellungen", (b.x + 40, b.y + 34), 32, TEXT, True)
        x, y = b.x + 50, b.y + 110
        for label, dy in (("Vollbild (F11)", 4), ("Musik", 62), ("Effekte", 122), ("Geist der Bestzeit", 184),
                          ("Vorsprung gegen Bot", 248)):
            text(surface, label, (x, y + dy), 20, MUTED, True)
        self.fullscreen.draw(surface)
        self.music.draw(surface)
        self.sfx.draw(surface)
        self.ghost.draw(surface)
        self.head.draw(surface)
        y = b.y + 410
        text(surface, "Steuerung", (x, y), 20, ACCENT, True)
        for i, line in enumerate(["A / D oder ← →  laufen   ·   W, Leertaste oder ↑  springen   ·   Enter  schießen",
                                  "Esc / P  Pause   ·   R  Neustart   ·   F11  Vollbild"]):
            text(surface, line, (x, y + 34 + 26 * i), 16, TEXT)
        text(surface, f"Spielstand: {self.app.progress.path}", (x, b.bottom - 100), 13, MUTED)
        self.done.draw(surface, mouse_pos())


# ===================================================================== editor
class EditorScene(Scene):
    """The level editor inside the app; Esc / quit returns to the menu."""

    def __init__(self, app):
        super().__init__(app)
        from jumpnrun.editor.app import EditorApp

        self.editor = EditorApp(None, (SCREEN_W, SCREEN_H), on_exit=self._exit)

    def enter(self) -> None:
        self.app.audio.music(None)

    def _exit(self) -> None:
        self.app.switch(MenuScene(self.app))

    def handle(self, event) -> None:
        if event.type == pygame.VIDEORESIZE:
            return  # the window scales the fixed-size surface
        if event.type == pygame.QUIT:
            self.editor.unsaved_then(self.app.quit)
            return
        self.editor.handle(event)

    def update(self, dt: float) -> None:
        self.editor.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        self.editor.draw(surface)

    def close(self) -> None:
        self.editor.keeper.stop()


