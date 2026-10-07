"""Phase 10: a level picture and a ghost video (16 bots at once) per measurement category - only allowed levels.

    OMP_NUM_THREADS=1 nice python3 scripts/videos10.py        # -> docs/lernen/medien/phase10/*.png / *.mp4

Test and sealed levels are never shown (only their sums may be reported); handmade8 test is replaced by an allowed
handmade8 dev level of the same series.
"""

from __future__ import annotations

import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "hide")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

OUT = ROOT / "docs/lernen/medien/phase10"
MODELS = {"phase10": ("models/phase10_kandidat_lehrer.zip", "Phase 10 (Lehrer-Kandidat)"),
          "p8": ("models/phase8_final.zip", "Phase 8")}


def _probe(skill):
    from jumpnrun.core.level import Level

    item = next(x for x in json.loads((ROOT / "levels/probes/v10.json").read_text())["levels"] if x["skill"] == skill)
    lv = Level.from_text(item["text"], name=item["name"])
    lv.needs_path = True
    return lv


def _schutz():
    from jumpnrun.rl.milestones import frozen_levels

    return frozen_levels("v3")[0][1]


def _mirror(path):
    from jumpnrun.core.level import Level
    from jumpnrun.levelgen.skills import mirror_level

    return mirror_level(Level.from_file(ROOT / path))


CATEGORIES = [
    # key, title, level factory, models, game-time limit (s)
    ("1_alt_dev", "Alte Dev-Level: hoehlendach", lambda: _file("levels/handmade8/hoehlendach.txt"), ["phase10", "p8"], 80),
    ("2_pruefung", "Prüfung", lambda: _file("levels/exam/level.txt"), ["phase10", "p8"], 150),
    ("3_schutz", "Schutz (Generator Stufe 10)", _schutz, ["phase10"], 80),
    ("4_waechter", "Wächter g2 (lang, Phase-8-Stil)", lambda: _file("levels/handmade10/g2.txt"), ["phase10", "p8"], 180),
    ("5_phase9_dev", "Phase-9-Dev: serpentine (Kanal)", lambda: _file("levels/handmade9/serpentine.txt", True),
     ["phase10", "p8"], 120),
    ("6_kanal_probe", "Kanal-Probe", lambda: _probe("kanal"), ["phase10", "p8"], 60),
    ("7_umkehren_probe", "Umkehren-Probe", lambda: _probe("umkehren"), ["phase10"], 60),
    ("8_ersatz_h8_test_doppelgabel", "Statt h8-Test: doppelgabel (h8-Dev, gleiche Serie)",
     lambda: _file("levels/handmade8/doppelgabel.txt"), ["phase10", "p8"], 90),
    ("9_gespiegelt_lang", "Gespiegelt: Wächter g0, Truhe links", lambda: _mirror("levels/handmade10/g0.txt"),
     ["phase10"], 120),
]


def _file(path, needs_path=False):
    from jumpnrun.core.level import Level

    lv = Level.from_file(ROOT / path)
    if needs_path:
        lv.needs_path = True
    return lv


def picture(key, title, level):
    """The whole level, wrapped into rows of at most 110 tiles, so long levels stay readable."""

    import pygame

    from jumpnrun.core.constants import TILE
    from jumpnrun.render.ghosts import GhostView
    from jumpnrun.render.video import init_headless

    init_headless()
    base = GhostView(level).base
    w, h = base.get_size()
    seg = 110 * TILE
    parts = [base.subsurface((x, 0, min(seg, w - x), h)) for x in range(0, w, seg)]
    scale = 1800 / min(w, seg)
    row_h = int(h * scale)
    canvas = pygame.Surface((int(min(w, seg) * scale), 44 + len(parts) * (row_h + 8)))
    canvas.fill((14, 12, 34))
    pygame.font.init()
    font = pygame.font.SysFont("Arial", 28, bold=True)
    small = pygame.font.SysFont("Arial", 18)
    canvas.blit(font.render(f"{title}  ({level.cols} Kacheln breit)", True, (255, 230, 120)), (10, 6))
    for i, part in enumerate(parts):
        y = 44 + i * (row_h + 8)
        canvas.blit(pygame.transform.smoothscale(part, (int(part.get_width() * scale), row_h)), (0, y))
        canvas.blit(small.render(f"Kachel {i * 110}-{min(level.cols, (i + 1) * 110)}", True, (230, 230, 230)), (8, y + 4))
    pygame.image.save(canvas, str(OUT / f"{key}.png"))


def video(job):
    idx, model_key = job
    key, title, factory, _, max_s = CATEGORIES[idx]
    import torch

    from jumpnrun.render.ghosts import GhostView
    from jumpnrun.render.video import VideoWriter, init_headless
    from jumpnrun.rl.modelinfo import load_model
    from jumpnrun.rl.watch import run_episode

    torch.set_num_threads(1)
    torch.manual_seed(0)
    level = factory()
    path, label = MODELS[model_key]
    model = load_model(ROOT / path)
    surface = init_headless()
    view = GhostView(level)
    out = OUT / f"{key}_{model_key}.mp4"
    with VideoWriter(str(out)) as vw:
        run = run_episode(model, level, 16, view, surface, label, title, vw.add, speed=3, max_seconds=max_s)
    wins = sum(1 for r in run.results if r and r["won"])
    return key, model_key, wins


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for key, title, factory, models, _ in CATEGORIES:
        picture(key, title, factory())
    if sys.argv[1:2] == ["bilder"]:
        return
    jobs = [(i, m) for i, c in enumerate(CATEGORIES) for m in c[3]]
    summary = {}
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as p:
        for key, model_key, wins in p.imap_unordered(video, jobs):
            summary.setdefault(key, {})[model_key] = f"{wins}/16"
            print(key, model_key, wins, "/ 16", flush=True)
    (OUT / "uebersicht.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
