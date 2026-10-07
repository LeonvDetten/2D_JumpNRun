"""Phase 10: ONE overview picture + ONE video over all measurement categories (allowed levels only).

    OMP_NUM_THREADS=1 nice python3 scripts/kompakt10.py      # -> docs/lernen/medien/phase10/uebersicht.png / .mp4

Picture: per category the whole level (wrapped into rows of at most 200 tiles) with the spots where the 16 bots of
the phase-10 teacher candidate died (red) or got stuck (yellow), plus wins phase 10 vs. P8.
Video: per category a time-lapse clip (~12 s) of the 16 bots, with a title card in front.
"""

from __future__ import annotations

import json
import math
import os
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "hide")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import videos10 as V  # noqa: E402

OUT = ROOT / "docs/lernen/medien/phase10"
TMP = OUT / "_clips"
KEEP = ["1_alt_dev", "2_pruefung", "3_schutz", "4_waechter", "5_phase9_dev", "6_kanal_probe",
        "8_ersatz_h8_test_doppelgabel", "9_gespiegelt_lang"]
CLIP_FRAMES = 360  # ~12 s at 30 fps
LABELS = {"1_alt_dev": "1  Alte Dev-Level", "2_pruefung": "2  Prüfung", "3_schutz": "3  Schutz",
          "4_waechter": "4  Wächter (lang)", "5_phase9_dev": "5  Phase-9-Dev (Umkehren/Kanäle)",
          "6_kanal_probe": "6  Kanal-Probe", "8_ersatz_h8_test_doppelgabel": "7  handmade8 (Ersatz: doppelgabel)",
          "9_gespiegelt_lang": "8  Gespiegelt lang (Truhe links)"}


def category(key):
    return next(c for c in V.CATEGORIES if c[0] == key)


def clip(key):
    import torch

    from jumpnrun.render.ghosts import GhostView
    from jumpnrun.render.video import VideoWriter, init_headless
    from jumpnrun.rl.modelinfo import load_model
    from jumpnrun.rl.watch import run_episode

    _, title, factory, _, max_s = category(key)
    torch.set_num_threads(1)
    torch.manual_seed(0)
    level = factory()
    model = load_model(ROOT / V.MODELS["phase10"][0])
    surface = init_headless()
    view = GhostView(level)
    speed = max(2, math.ceil(max_s * 30 / CLIP_FRAMES))
    TMP.mkdir(parents=True, exist_ok=True)
    with VideoWriter(str(TMP / f"{key}.mp4")) as vw:
        run = run_episode(model, level, 16, view, surface, f"Phase 10 – Zeitraffer x{speed}",
                          title, vw.add, speed=speed, max_seconds=max_s)
    ends = []
    for env, res in zip(run.envs, run.results):
        p = env.sim.player
        out = res["outcome"] if res else "running"
        ends.append([p.x + p.w // 2, p.y + p.h // 2, out])
    wins = sum(1 for r in run.results if r and r["won"])
    return key, wins, ends


def title_card(text, sub):
    import pygame

    from jumpnrun.render.video import init_headless

    surface = init_headless()
    surface.fill((14, 12, 34))
    pygame.font.init()
    big = pygame.font.SysFont("Arial", 64, bold=True)
    small = pygame.font.SysFont("Arial", 40)
    w, h = surface.get_size()
    t = big.render(text, True, (255, 230, 120))
    s = small.render(sub, True, (230, 230, 230))
    surface.blit(t, ((w - t.get_width()) // 2, h // 2 - 70))
    surface.blit(s, ((w - s.get_width()) // 2, h // 2 + 20))
    return surface


def picture(results, p8):
    import pygame

    from jumpnrun.core.constants import TILE
    from jumpnrun.render.ghosts import GhostView
    from jumpnrun.render.video import init_headless

    init_headless()
    pygame.font.init()
    font = pygame.font.SysFont("Arial", 26, bold=True)
    small = pygame.font.SysFont("Arial", 20)
    width, seg_tiles = 1800, 200
    scale = width / (seg_tiles * TILE)
    panels = []
    for key in KEEP:
        _, title, factory, _, _ = category(key)
        level = factory()
        base = GhostView(level).base.copy()
        for x, y, out in results[key]["ends"]:
            if out == "won":
                continue
            color = (255, 40, 40) if out.startswith("died") else (255, 220, 0)
            pygame.draw.circle(base, color, (int(x), int(min(y, base.get_height() - 40))), 70, 18)
        w, h = base.get_size()
        rows = [base.subsurface((x, 0, min(seg_tiles * TILE, w - x), h)) for x in range(0, w, seg_tiles * TILE)]
        row_h = int(h * scale)
        panel = pygame.Surface((width, 40 + len(rows) * (row_h + 4)))
        panel.fill((14, 12, 34))
        score = f"Phase 10: {results[key]['wins']}/16"
        if key in p8:
            score += f"   P8: {p8[key]}"
        panel.blit(font.render(LABELS[key], True, (255, 230, 120)), (10, 6))
        panel.blit(small.render(f"{title} · {level.cols} Kacheln · {score}", True, (230, 230, 230)), (520, 10))
        for i, part in enumerate(rows):
            panel.blit(pygame.transform.smoothscale(part, (int(part.get_width() * scale), row_h)),
                       (0, 40 + i * (row_h + 4)))
        panels.append(panel)
    legend_h = 40
    canvas = pygame.Surface((width, legend_h + sum(p.get_height() + 12 for p in panels)))
    canvas.fill((8, 6, 20))
    canvas.blit(small.render("Phase 10 – je Kategorie 16 Bots des Lehrer-Kandidaten. Kreise = wo Bots scheitern: rot Absturz/Gegner,"
                             " gelb steckt fest/Zeit um. Truhe = braunes Kästchen (bei 8 links).",
                             True, (230, 230, 230)), (10, 10))
    y = legend_h
    for p in panels:
        canvas.blit(p, (0, y))
        y += p.get_height() + 12
    pygame.image.save(canvas, str(OUT / "uebersicht.png"))


def main():
    import imageio
    import numpy as np
    import pygame

    from jumpnrun.render.video import VideoWriter

    p8 = {k: v.get("p8") for k, v in json.loads((OUT / "uebersicht.json").read_text()).items() if v.get("p8")}
    results = {}
    with Pool(4) as pool:
        for key, wins, ends in pool.imap_unordered(clip, KEEP):
            results[key] = {"wins": wins, "ends": ends}
            print(key, wins, "/ 16", flush=True)
    (OUT / "uebersicht_enden.json").write_text(json.dumps(results))
    picture(results, p8)
    with VideoWriter(str(OUT / "uebersicht.mp4")) as vw:
        for key in KEEP:
            sub = f"Phase 10: {results[key]['wins']}/16 im Ziel" + (f"   ·   P8: {p8[key]}" if key in p8 else "")
            vw.add(title_card(LABELS[key], sub), repeat=45)
            reader = imageio.get_reader(str(TMP / f"{key}.mp4"))
            for frame in reader:
                surf = pygame.surfarray.make_surface(np.transpose(frame, (1, 0, 2)))
                vw.add(pygame.transform.smoothscale(surf, (1520, 800)))
            reader.close()
    for f in TMP.glob("*.mp4"):
        f.unlink()
    TMP.rmdir()
    (OUT / "uebersicht_ergebnisse.json").write_text(json.dumps({k: v["wins"] for k, v in results.items()}, indent=1))
    print("fertig")


if __name__ == "__main__":
    if sys.argv[1:] == ["bild"]:
        p8 = {k: v.get("p8") for k, v in json.loads((OUT / "uebersicht.json").read_text()).items() if v.get("p8")}
        picture(json.loads((OUT / "uebersicht_enden.json").read_text()), p8)
    else:
        main()
