"""Pictures and videos for the README / docs, rendered from the real game (reproducible).

    python scripts/make_readme_media.py measure      # exam success per training stage -> docs/medien/pruefung_messung.json
    python scripts/make_readme_media.py hero         # the bot plays the 2023 exam level -> bot_pruefung_2023.mp4/.gif
    python scripts/make_readme_media.py progress     # one clip per training stage -> bot_lernfortschritt.mp4/.gif
    python scripts/make_readme_media.py ghosts       # 32 bots at once -> geister_32.gif
    python scripts/make_readme_media.py banner       # title picture -> banner.png
    python scripts/make_readme_media.py collage      # app screenshots -> app_collage.jpg, editor_weg.jpg
    python scripts/make_readme_media.py chart        # learning curve -> lernkurve.png (needs measure)
    python scripts/make_readme_media.py all

Needs PyTorch + stable-baselines3 (bot), imageio + ffmpeg (videos), matplotlib (chart). Runs headless.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "hide")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from jumpnrun.core.constants import FPS, SCREEN_H, SCREEN_W  # noqa: E402
from jumpnrun.core.level import Level  # noqa: E402
from jumpnrun.core.sim import Status  # noqa: E402

OUT = ROOT / "docs" / "medien"
EXAM = ROOT / "levels" / "exam" / "level.txt"
TEMPERATURE = 0.3

# training stages shown in the README (model file, label, one-line description)
STAGES = [
    ("phase1", "Phase 1", "laufen und springen"),
    ("phase2", "Phase 2", "Gegner und Plattformen"),
    ("phase3", "Phase 3", "erster Generalist"),
    ("phase5", "Phase 5", "vom Löser abgeschaut"),
    ("phase6_durchbruch", "Phase 6", "Übersichtskarte, lange Level"),
    ("phase7_final", "Phase 7", "zwei Netze, Abzweige"),
    ("phase8_final", "Phase 8", "ehrlich gemessen"),
    ("phase11_kandidat", "Phase 11", "Generalist"),
    ("phase12_kandidat", "Phase 12", "Generalist-Schüler"),
    ("space_pirate_bot", "Phase 13", "aktueller Bot (Links-Training)"),
]
CLIP_STAGES = ["phase1", "phase3", "phase6_durchbruch", "space_pirate_bot"]


def init_display() -> pygame.Surface:
    pygame.init()
    pygame.display.set_mode((1, 1))
    pygame.font.init()
    return pygame.Surface((SCREEN_W, SCREEN_H))


def model(name: str):
    from jumpnrun.rl.modelinfo import load_model

    return load_model(ROOT / "models" / f"{name}.zip")


def to_gif(mp4: Path, gif: Path, speed: float, fps: int = 10, width: int = 600, colors: int = 72,
           crop_h: int = 0) -> None:
    """MP4 -> small GIF (ffmpeg with an own palette); crop_h keeps only the top rows of the (half-size) video."""

    crop = f"crop=iw:{crop_h}:0:0," if crop_h else ""
    vf = (f"{crop}setpts=PTS/{speed},fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
          f"[a]palettegen=max_colors={colors}:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", vf, "-loop", "0", str(gif)], check=True)
    print(f"  {gif.relative_to(ROOT)}: {gif.stat().st_size / 1e6:.1f} MB")


def shrink_mp4(mp4: Path, crf: int = 30) -> None:
    """Re-encode smaller for the repo (H.264, web-friendly)."""

    tmp = mp4.with_name("_" + mp4.name)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-c:v", "libx264", "-crf", str(crf),
                    "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(mp4)
    print(f"  {mp4.relative_to(ROOT)}: {mp4.stat().st_size / 1e6:.1f} MB")


# --------------------------------------------------------------------------- measure
def measure(attempts: int = 64, temperatures=(1.0, TEMPERATURE)) -> None:
    """Exam success per training stage, at T = 1 (the policy as trained, how phases 1-11 were measured) and at
    T = 0.3 (sharpened, how the bot plays since phase 12)."""

    from jumpnrun.rl.modelinfo import env_kwargs
    from jumpnrun.rl.watch import GhostRun

    level = Level.from_file(EXAM)
    rows = []
    for name, label, desc in STAGES:
        m = model(name)
        row = dict(model=f"models/{name}.zip", stage=label, description=desc, attempts=attempts)
        for temp in temperatures:
            t0 = time.time()
            run = GhostRun(level, attempts, **env_kwargs(m))
            while not run.done():
                for _ in run.play_step(m, temperature=temp):
                    pass
            won = [s for s in run.sims if s.status == Status.WON]
            key = f"t{str(temp).replace('.', '')}"
            row[key] = dict(won=len(won), rate=len(won) / attempts,
                            mean_progress=sum(min(1.0, s.max_x / level.goal_x) for s in run.sims) / attempts,
                            median_win_seconds=sorted(s.frame for s in won)[len(won) // 2] / FPS if won else None)
            print(f"{label:9s} {name:22s} T={temp}: {len(won):3d}/{attempts}  Fortschritt "
                  f"{row[key]['mean_progress']:.0%}  ({time.time() - t0:.0f}s)", flush=True)
        best = max((row[k] for k in row if k.startswith("t")), key=lambda r: r["rate"])
        row.update(won=best["won"], rate=best["rate"])
        rows.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    data = dict(level="levels/exam/level.txt", temperatures=list(temperatures), attempts_per_model=attempts,
                measured=time.strftime("%Y-%m-%d"), note="seeds 0..attempts-1 per temperature, jumpnrun.rl.watch.GhostRun; "
                "rate/won = the better of both temperatures", results=rows)
    (OUT / "pruefung_messung.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def measured() -> dict:
    path = OUT / "pruefung_messung.json"
    return {r["model"].split("/")[-1][:-4]: r for r in json.loads(path.read_text())["results"]} if path.exists() else {}


# --------------------------------------------------------------------------- overlays
def label_box(surface, lines, pos=(24, 20), anchor="topleft"):
    from jumpnrun.app.gfx import glass_panel
    from jumpnrun.ui.widgets import font

    fonts = [font(30, True)] + [font(20)] * (len(lines) - 1)
    images = [f.render(t, True, c) for f, (t, c) in zip(fonts, lines)]
    w = max(i.get_width() for i in images) + 36
    h = sum(i.get_height() for i in images) + 14 * len(images) + 10
    rect = pygame.Rect(0, 0, w, h)
    setattr(rect, anchor, pos)
    glass_panel(surface, rect, 205, None, 14)
    y = rect.y + 12
    for img in images:
        surface.blit(img, (rect.x + 18, y))
        y += img.get_height() + 12


def progress_bar(surface, level, x_now, frame):
    from jumpnrun.app.gfx import CYAN, GOLD, glass_panel, star
    from jumpnrun.app.progress import format_time
    from jumpnrun.ui.widgets import font

    rect = pygame.Rect(SCREEN_W - 560, 20, 536, 70)
    glass_panel(surface, rect, 205, None, 14)
    t = font(30, True).render(format_time(frame), True, (235, 240, 250))
    surface.blit(t, (rect.x + 18, rect.centery - t.get_height() // 2))
    track = pygame.Rect(rect.x + 180, rect.centery - 4, 310, 8)
    pygame.draw.rect(surface, (50, 56, 84), track, border_radius=4)
    k = max(0.0, min(1.0, (x_now - level.spawn[0]) / max(1, level.goal_x - level.spawn[0])))
    done = track.copy()
    done.w = max(8, int(track.w * k))
    pygame.draw.rect(surface, CYAN, done, border_radius=4)
    star(surface, (track.right + 16, track.centery), 11, GOLD)


# --------------------------------------------------------------------------- hero
def hero() -> None:
    from jumpnrun.render.renderer import Renderer
    from jumpnrun.render.video import VideoWriter
    from jumpnrun.rl.modelinfo import env_kwargs
    from jumpnrun.rl.watch import GhostRun

    surface = init_display()
    level = Level.from_file(EXAM)
    m = model("space_pirate_bot")
    for seed in range(20):  # the first seed in which the bot wins (it wins ~98 % at T = 0.3)
        run = GhostRun(level, 1, **env_kwargs(m))
        run.obs = [run.envs[0].reset(seed=seed)[0]]
        frames = []
        while not run.done():
            for _ in run.play_step(m, temperature=TEMPERATURE):
                frames.append(run.sims[0].clone())
        if run.sims[0].status == Status.WON:
            break
    print(f"hero: seed {seed}, {len(frames) / FPS:.1f} s game time")
    renderer = Renderer()
    info = json.loads((ROOT / "models" / "space_pirate_bot.json").read_text(encoding="utf-8"))
    exam = info.get("kennzahlen", {}).get("pruefung_t03")
    sub = f"{exam:.0%} Erfolg auf diesem Level (256 Versuche)".replace(".", ",") if exam else "Reinforcement Learning (PPO)"
    mp4 = OUT / "bot_pruefung_2023.mp4"
    with VideoWriter(str(mp4), scale=0.5) as video:
        for i, sim in enumerate(frames + [frames[-1]] * 45):
            renderer.draw(surface, sim, max(0, i - len(frames)) if sim.status == Status.WON else 0)
            label_box(surface, [("Der Bot spielt das Original-Level von 2023", (255, 220, 140)),
                                (f"Space Pirate Bot · {sub}", (200, 210, 230))], (SCREEN_W - 24, SCREEN_H - 24),
                      "bottomright")
            progress_bar(surface, level, sim.player.x, min(i, len(frames) - 1))
            video.add(surface)
    print(f"  {mp4.relative_to(ROOT)}: {mp4.stat().st_size / 1e6:.1f} MB")
    to_gif(mp4, OUT / "bot_pruefung_2023.gif", speed=3.0, fps=10, width=600, colors=72)
    shrink_mp4(mp4)


# --------------------------------------------------------------------------- learning progress
def title_card(surface, top: str, bottom: str):
    from jumpnrun.app.gfx import fancy_text
    from jumpnrun.ui.widgets import font

    surface.fill((10, 10, 28))
    t = fancy_text(top, 96, glow_color=(255, 170, 60))
    surface.blit(t, t.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 50)))
    b = font(36, True).render(bottom, True, (200, 220, 255))
    surface.blit(b, b.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 70)))


def progress() -> None:
    from jumpnrun.render.ghosts import GhostView
    from jumpnrun.render.video import VideoWriter
    from jumpnrun.rl.watch import run_episode

    surface = init_display()
    level = Level.from_file(EXAM)
    view = GhostView(level)
    rates = measured()
    labels = {name: (label, desc) for name, label, desc in STAGES}
    mp4 = OUT / "bot_lernfortschritt.mp4"
    with VideoWriter(str(mp4), scale=0.5) as video:
        title_card(surface, "So hat der Bot gelernt", "Prüfungslevel 2023 · je 16 Versuche gleichzeitig")
        video.add(surface, repeat=60)
        for name in CLIP_STAGES:
            label, desc = labels[name]
            r = rates.get(name)
            rate = f"schafft {r['rate']:.0%} (64 Versuche)".replace(".", ",") if r else ""
            # each stage plays in the way it plays best (early nets need T = 1, see the measurement)
            temp = 1.0 if r and r["t10"]["rate"] > r["t03"]["rate"] else TEMPERATURE
            title_card(surface, label, f"{desc} · {rate}")
            video.add(surface, repeat=40)
            last = name == CLIP_STAGES[-1]
            run_episode(model(name), level, 16, view, surface, f"{label}: {desc}", f"Erfolgsquote gemessen: {rate}",
                        video.add, speed=3, max_seconds=100 if last else 25, temperature=temp)
    print(f"  {mp4.relative_to(ROOT)}: {mp4.stat().st_size / 1e6:.1f} MB")
    to_gif(mp4, OUT / "bot_lernfortschritt.gif", speed=3.0, fps=8, width=520, colors=64, crop_h=330)
    shrink_mp4(mp4)


def ghosts() -> None:
    from jumpnrun.render.ghosts import GhostView
    from jumpnrun.render.video import VideoWriter
    from jumpnrun.rl.watch import run_episode

    surface = init_display()
    level = Level.from_file(EXAM)
    tmp = OUT / "_geister_32.mp4"
    with VideoWriter(str(tmp), scale=0.5) as video:
        run_episode(model("space_pirate_bot"), level, 32, GhostView(level), surface,
                    "32 Bots gleichzeitig – Prüfungslevel 2023", "Space Pirate Bot, Temperatur 0,3", video.add,
                    speed=4, max_seconds=100, temperature=TEMPERATURE)
    to_gif(tmp, OUT / "geister_32.gif", speed=2.0, fps=8, width=520, colors=64, crop_h=330)
    tmp.unlink()


# --------------------------------------------------------------------------- banner
def banner() -> None:
    """1280 x 400 title picture from the full-resolution source images (the in-game sprites are tiny)."""

    from jumpnrun.app.gfx import Logo, glass_panel
    from jumpnrun.render.assets import IMG_DIR, get_assets
    from jumpnrun.ui.widgets import font

    init_display()
    W, H = 1280, 400
    surface = pygame.Surface((W, H))
    bg = pygame.image.load(str(IMG_DIR / "background_img" / "bg.jpg")).convert()
    bg = pygame.transform.smoothscale(bg, (W, int(bg.get_height() * W / bg.get_width())))
    surface.blit(bg, (0, -(bg.get_height() - H) // 2 - 40))
    shade = pygame.Surface((W, H), pygame.SRCALPHA)
    shade.fill((6, 8, 26, 70))
    surface.blit(shade, (0, 0))
    ground = pygame.transform.smoothscale(pygame.image.load(str(IMG_DIR / "ground_img" / "spaceground.png")).convert_alpha(),
                                          (48, 48))
    for x in range(0, W, 48):
        surface.blit(ground, (x, H - 48))
    hero_src = pygame.image.load(str(IMG_DIR / "player_img" / "2_entity_000_IDLE_000.png")).convert_alpha()
    hero_img = pygame.transform.smoothscale(hero_src.subsurface(pygame.Rect(200, 250, 825, 850)), (150, 155))
    surface.blit(hero_img, (70, H - 48 - 155))
    enemy = pygame.transform.scale(pygame.image.load(str(IMG_DIR / "enemy_img" / "e1_l0.png")).convert_alpha(), (96, 96))
    chest = pygame.transform.scale(pygame.image.load(str(IMG_DIR / "chest_img" / "chest1_0.png")).convert_alpha(), (105, 74))
    surface.blit(enemy, (W - 250, H - 48 - 96))
    surface.blit(chest, (W - 140, H - 48 - 74))
    Logo(get_assets()).draw(surface, (W // 2, 168), 0.0, 1.0)
    sub = font(24, True).render("Ein Jump'n'Run – und ein Bot, der es selbst gelernt hat", True, (232, 238, 255))
    box = sub.get_rect(center=(W // 2, 318)).inflate(36, 16)
    glass_panel(surface, box, 170, None, 14)
    surface.blit(sub, sub.get_rect(center=box.center))
    pygame.image.save(surface, str(OUT / "banner.png"))
    print(f"  docs/medien/banner.png: {(OUT / 'banner.png').stat().st_size / 1e6:.1f} MB")


# --------------------------------------------------------------------------- app collage
def collage() -> None:
    os.environ["SPACE_PIRATE_HOME"] = str(OUT / "_collage_home")
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    from jumpnrun.app import scenes as sc
    from jumpnrun.app.main import GameApp
    from jumpnrun.core.actions import BOT_ACTIONS_V3
    from jumpnrun.editor.model import load_solution

    app = GameApp(screen)

    def run(sec, dt=1 / 60):
        for _ in range(int(sec / dt)):
            app.update(dt)

    shots = []

    def shot(caption):
        app.draw(screen)
        shots.append((screen.copy(), caption))

    run(0.9)
    shot("Ladescreen")
    run(1.6)
    app.bot.wait(120)
    run(3.0)
    shot("Hauptmenü mit Bot-Demo")
    app.top.activate("single")
    run(0.5)
    app.top.tabs.index = app.top.tabs.labels.index("Test-Serie")
    run(0.1)
    shot("Levelauswahl: Bestzeit, Sterne, Bot-Zeit")
    # a won run with the proven way (3 stars), then the result screen
    sol = [BOT_ACTIONS_V3[a] for a in load_solution(ROOT / "levels/test_serie/berg.txt") for _ in range(2)]
    frames = iter(sol)
    sc.keys_to_action = lambda pressed: next(frames, BOT_ACTIONS_V3[0])
    entry = next(e for e in app.tabs["Test-Serie"] if e.path.stem == "berg")
    app.switch(sc.GameScene(app, entry, "single", 0, "Test-Serie"))
    run(36)
    shot("Ergebnis mit Sternen")
    frames = iter([BOT_ACTIONS_V3[0]] * 50 + sol)
    app.top.activate("again")
    run(3.4 + 9)
    shot("Bestzeit-Geist läuft mit")
    frames = iter([BOT_ACTIONS_V3[0]] * 12 + sol)  # the bot way, a little late: the bot runs just ahead
    app.switch(sc.GameScene(app, entry, "bot", 0, "Test-Serie"))
    run(0.5 + 3.2 + 6.2)
    shot("Rennen gegen den Bot")
    app.switch(sc.EditorScene(app))
    run(0.5)
    app.top.editor.open(ROOT / "levels/exam/level.txt")
    app.top.editor.scroll = 128
    run(0.3)
    shot("Level-Editor: bewiesener Bot-Weg")
    editor = pygame.transform.smoothscale(shots[-1][0], (1140, 600))
    pygame.image.save(editor, str(OUT / "editor_weg.jpg"))
    # compose 2 columns x 4 rows (first shot = loading screen is skipped for space)
    picks = shots[1:]
    w, h = 760, 400
    cols, rows = 2, -(-len(picks) // 2)
    sheet = pygame.Surface((cols * w + (cols + 1) * 24, rows * (h + 46) + 24))
    sheet.fill((13, 17, 30))
    from jumpnrun.ui.widgets import font

    for i, (img, caption) in enumerate(picks):
        r, c = divmod(i, cols)
        x, y = 24 + c * (w + 24), 24 + r * (h + 46)
        sheet.blit(pygame.transform.smoothscale(img, (w, h)), (x, y))
        pygame.draw.rect(sheet, (70, 90, 140), (x, y, w, h), 2)
        sheet.blit(font(22, True).render(caption, True, (220, 228, 245)), (x + 4, y + h + 10))
    path = OUT / "app_collage.jpg"
    pygame.image.save(sheet, str(path))
    print(f"  {path.relative_to(ROOT)}: {path.stat().st_size / 1e6:.1f} MB")
    import shutil

    shutil.rmtree(OUT / "_collage_home", ignore_errors=True)


# --------------------------------------------------------------------------- chart
def chart() -> None:
    """Grouped bars: exam success per training stage at T = 1 and T = 0.3 (palette validated with the dataviz
    validator: #2a78d6 / #eb6834 pass CVD and contrast checks on a light surface)."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    data = json.loads((OUT / "pruefung_messung.json").read_text())
    rows = data["results"]
    labels = [r["stage"].replace("Phase ", "P") for r in rows]
    t1 = [100 * r["t10"]["rate"] for r in rows]
    t03 = [100 * r["t03"]["rate"] for r in rows]
    surface, ink, muted, grid = "#fcfcfb", "#0b0b0b", "#52514e", "#e7e6e2"
    blue, orange = "#2a78d6", "#eb6834"
    fig, ax = plt.subplots(figsize=(10, 4.4), dpi=150)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    width, gap = 0.36, 0.03

    def bar(x, h, color):  # thin bar with rounded top, anchored to the baseline
        if h < 3:  # (almost) zero: a thin line on the baseline, rounded bar ends would look broken
            ax.plot([x - width / 2 + 0.02, x + width / 2 - 0.02], [max(0.5, h), max(0.5, h)], color=color, lw=2.5,
                    solid_capstyle="round", zorder=3)
            return
        ax.add_patch(FancyBboxPatch((x - width / 2, 0), width, h, boxstyle="round,pad=0,rounding_size=0.06",
                                    mutation_aspect=40, color=color, lw=0, zorder=3))

    for i, (a1, a3) in enumerate(zip(t1, t03)):
        bar(i - width / 2 - gap / 2, a1, blue)
        bar(i + width / 2 + gap / 2, a3, orange)
        best = max(a1, a3)
        x = i - width / 2 - gap / 2 if a1 >= a3 else i + width / 2 + gap / 2
        ax.text(x, best + 2, f"{best:.0f} %", ha="center", va="bottom", fontsize=8.5, color=ink)
    ax.set_xlim(-0.6, len(rows) - 0.4)
    ax.set_ylim(0, 112)
    ax.set_xticks(range(len(rows)), labels)
    ax.set_yticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100 %"])
    ax.yaxis.grid(True, color=grid, lw=0.8, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(grid)
    ax.tick_params(colors=muted, length=0, labelsize=9)
    ax.set_title(f"Prüfungslevel 2023 – Kiste erreicht, je Lernstand ({data['attempts_per_model']} Versuche je "
                 f"Spielweise, gemessen {'.'.join(reversed(data['measured'].split('-')))})", loc="left", fontsize=11, color=ink, pad=14)
    from matplotlib.patches import Patch

    ax.legend(handles=[Patch(color=blue, label="Temperatur 1 (Netz wie trainiert)"),
                       Patch(color=orange, label="Temperatur 0,3 (geschärft, Spielweise seit Phase 12)")],
              frameon=False, loc="upper left", fontsize=9, labelcolor=ink)
    fig.tight_layout()
    path = OUT / "lernkurve.png"
    fig.savefig(path, facecolor=surface)
    print(f"  {path.relative_to(ROOT)}: {path.stat().st_size / 1e6:.2f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("what", nargs="+", choices=["measure", "hero", "progress", "ghosts", "banner", "collage",
                                                    "chart", "all"])
    parser.add_argument("--attempts", type=int, default=64)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    todo = ["measure", "chart", "hero", "progress", "ghosts", "banner", "collage"] if "all" in args.what else args.what
    for what in todo:
        print(f"== {what}", flush=True)
        if what == "measure":
            measure(args.attempts)
        else:
            globals()[what]()


if __name__ == "__main__":
    main()
