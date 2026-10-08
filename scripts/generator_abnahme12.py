"""Phase 12, decision point E0: acceptance of generator v11 - diversity, solvability, difficulty, distance to
measurement levels, plus a gallery for Leon.

    OMP_NUM_THREADS=1 python3 scripts/generator_abnahme12.py [procs]
    -> runs/phase12/abnahme.json, docs/lernen/medien/phase12/generator_galerie.png

Criteria (plan):
    solvable      solver proof on the probe set (levels/probes/v13_hard.json stats) - all probes are proven
    diversity     >= 12 different blocks, none above 15 % of all blocks, >= 60 different block pairs in a row,
                  way profile (direction changes, height span, rises) more spread than v9 tier 12 / v10 tier 13
    difficulty    P8, phase 11 and Neustart win <= 50 % per new category (jumps, structures), but > 0
    distance      no v11 level has the hash of an exam / dev / probe / guard level
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "hide")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
OUT = ROOT / "runs/phase12/abnahme.json"
GALLERY = ROOT / "docs/lernen/medien/phase12/generator_galerie.png"
MODELS = {"p8": "models/phase8_final.zip", "phase11": "models/phase11_kandidat.zip",
          "neustart": "models/neustart_kandidat_pruefung.zip"}
N = 500


def way_profile(level):
    from jumpnrun.levelgen.distmap import DistanceMap
    from jumpnrun.levelgen.solver import way_cells

    dm = DistanceMap(level)
    if not dm.reachable:
        return None
    start = min(dm.dist, key=lambda c: (abs(c[0] - level.spawn[0] // 40), abs(dm.dist[c] - (dm.start or 0))))
    cells = way_cells(dm, start)
    dirs = [1 if b[0] > a[0] else -1 for a, b in zip(cells, cells[1:]) if b[0] != a[0]]
    changes = sum(1 for a, b in zip(dirs, dirs[1:]) if a != b)
    rows = [c[1] for c in cells]
    rises = sum(1 for a, b in zip(cells, cells[1:]) if b[1] < a[1])
    return {"richtungswechsel": changes, "hoehenspanne": max(rows) - min(rows),
            "aufstiege_je_100": round(100 * rises / max(1, level.cols), 2)}


def _spread(values):
    import numpy as np

    v = np.array(values, float)
    return {"mittel": round(float(v.mean()), 2), "std": round(float(v.std()), 2), "verschieden": len(set(values))}


def _level_job(i):
    from jumpnrun.levelgen import generator as G
    from jumpnrun.levelgen.hard import HardSource

    rng = random.Random(f"abnahme12:{i}")
    lv, _ = HardSource()(rng)
    out = {"blocks": lv.blocks, "profil": way_profile(lv), "hash": hashlib.sha256(lv.to_text().encode()).hexdigest()}
    ref = {}
    for name, tier, var in (("v9_t12", 12, "v9"), ("v10_t13", 13, "v10")):
        ref[name] = way_profile(G.generate(tier, 4_000_000_000 + i, var))
    out["ref"] = ref
    return out


def _model_job(args):
    import numpy as np
    import torch

    from jumpnrun.core.level import Level
    from jumpnrun.rl.evaluate import evaluate_levels
    from jumpnrun.rl.modelinfo import load_model

    tag, path = args
    torch.set_num_threads(1)
    probes = json.loads((ROOT / "levels/probes/v13_hard.json").read_text())["levels"]
    out = {}
    model = load_model(ROOT / path)
    for fam in ("spruenge", "strukturen", "gemischt", "lang"):
        lv = [Level.from_text(p["text"]) for p in probes if p["skill"] == fam]
        for x in lv:
            x.needs_path = True
        np.random.seed(0)
        torch.manual_seed(0)
        res = evaluate_levels(model, lv * 2, deterministic=False)
        out[fam] = {"won": sum(int(r["won"]) for r in res), "of": len(res),
                    "fortschritt": round(float(np.mean([r["progress"] for r in res])), 3)}
    return tag, out


def gallery(n: int = 24):
    """Clear tile maps (no game graphics): blocks grey, enemies red, start green, chest gold."""

    from PIL import Image, ImageDraw, ImageFont

    from jumpnrun.levelgen.hard import make_hard_level

    px, per_row, width = 8, 225, 1800
    colors = {"B": (150, 150, 160), "E": (230, 60, 60), "P": (60, 220, 90), "C": (250, 200, 40)}
    fams = ["spruenge"] * 8 + ["strukturen"] * 8 + ["gemischt"] * 6 + ["lang"] * 2
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    panels = []
    for i, fam in enumerate(fams[:n]):
        lv = make_hard_level(fam, f"galerie12:{fam}:{i}")
        lines = lv.to_text().splitlines()
        cols = max(len(l) for l in lines)
        rows = -(-cols // per_row)
        h = 22 + rows * (len(lines) * px + 6)
        img = Image.new("RGB", (width, h), (18, 16, 36))
        d = ImageDraw.Draw(img)
        d.text((6, 3), f"{i + 1}. {fam} ({cols} Kacheln): " + ", ".join(dict.fromkeys(lv.blocks)), fill=(255, 230, 120),
                font=font)
        for k in range(rows):
            y0 = 22 + k * (len(lines) * px + 6)
            d.rectangle([0, y0, min(per_row, cols - k * per_row) * px, y0 + len(lines) * px - 1], fill=(30, 30, 60))
            for r, line in enumerate(lines):
                for c in range(k * per_row, min(len(line), (k + 1) * per_row)):
                    ch = line[c]
                    if ch in colors:
                        x = (c - k * per_row) * px
                        d.rectangle([x, y0 + r * px, x + px - 1, y0 + r * px + px - 1], fill=colors[ch])
        panels.append(img)
    canvas = Image.new("RGB", (width, sum(p.height + 10 for p in panels)), (8, 6, 20))
    y = 0
    for p in panels:
        canvas.paste(p, (0, y))
        y += p.height + 10
    GALLERY.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(GALLERY)


def measurement_hashes():
    from jumpnrun.core.level import Level

    h = set()
    paths = [ROOT / "levels/exam/level.txt", *sorted((ROOT / "levels/test_serie").glob("*.txt"))]
    for folder in ("handmade8", "handmade9"):
        split = json.loads((ROOT / "levels" / folder / "split.json").read_text())
        paths += [ROOT / "levels" / folder / f"{n}.txt" for n in split["dev"]]
    g = json.loads((ROOT / "levels/handmade10/split.json").read_text())
    paths += [ROOT / "levels/handmade10" / f"{n}.txt" for n in g["val"] + g["val_plus"]]
    for p in paths:
        h.add(hashlib.sha256(Level.from_file(p).to_text().encode()).hexdigest())
    for probe in sorted((ROOT / "levels/probes").glob("*.json")):
        for item in json.loads(probe.read_text()).get("levels", []):
            if probe.name != "v13_hard.json":
                h.add(hashlib.sha256(Level.from_text(item["text"]).to_text().encode()).hexdigest())
    return h


def main():
    procs = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    with Pool(procs) as pool:
        levels = pool.map(_level_job, range(N), chunksize=10)
        models = dict(pool.map(_model_job, list(MODELS.items())))
    blocks = Counter(b for lv in levels for b in lv["blocks"])
    total = sum(blocks.values())
    pairs = Counter((a, b) for lv in levels for a, b in zip(lv["blocks"], lv["blocks"][1:]))
    prof = {k: [lv["profil"][k] for lv in levels if lv["profil"]] for k in ("richtungswechsel", "hoehenspanne",
                                                                            "aufstiege_je_100")}
    ref = {name: {k: [lv["ref"][name][k] for lv in levels if lv["ref"][name]] for k in prof}
           for name in ("v9_t12", "v10_t13")}
    stats = json.loads((ROOT / "levels/probes/v13_hard.json").read_text())["stats"]
    clash = len({lv["hash"] for lv in levels} & measurement_hashes())
    crit = {
        "loesbar": {"proben": stats, "ok": all(s["genommen"] >= (12 if f == "lang" else 24) for f, s in stats.items())},
        "vielfalt": {
            "bausteine": len(blocks), "max_anteil": round(max(blocks.values()) / total, 3),
            "paare": len(pairs), "anteile": {k: round(v / total, 3) for k, v in blocks.most_common()},
            "wegprofil": {k: _spread(v) for k, v in prof.items()},
            "wegprofil_ref": {n: {k: _spread(v) for k, v in r.items()} for n, r in ref.items()},
        },
        "schwierigkeit": models,
        "abstand": {"gleiche_hashes": clash, "ok": clash == 0},
    }
    v = crit["vielfalt"]
    v["ok"] = (v["bausteine"] >= 12 and v["max_anteil"] <= 0.15 and v["paare"] >= 60
               and all(v["wegprofil"][k]["std"] > max(v["wegprofil_ref"][n][k]["std"] for n in ref)
                       for k in ("richtungswechsel", "hoehenspanne")))
    new = ("spruenge", "strukturen")
    crit["schwierigkeit_ok"] = all(0 < m[f]["won"] / m[f]["of"] <= 0.5 for m in models.values() for f in new)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(crit, indent=1, ensure_ascii=False))
    gallery()
    print(json.dumps({k: (x.get("ok") if isinstance(x, dict) else x) for k, x in crit.items()}, ensure_ascii=False))
    print("Bausteine", v["bausteine"], "max", v["max_anteil"], "Paare", v["paare"])
    print("Wegprofil", json.dumps(v["wegprofil"]), "Ref", json.dumps(v["wegprofil_ref"]))
    for tag, m in models.items():
        print(tag, {f: f"{x['won']}/{x['of']}" for f, x in m.items()})


if __name__ == "__main__":
    main()
