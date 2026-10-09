"""Phase 12 scorecard: 8 categories + one generalist value, one picture (Leon: "simple, easy to read").

    python3 -m jumpnrun.rl.scorecard12 eval models/phase8_final.zip --tag p8 --procs 4   # -> runs/phase12/score_<tag>.json
    python3 -m jumpnrun.rl.scorecard12 bild [--run runs/phase12_schueler]               # -> runs/phase12/scorecard.png

Categories (each the mean of its components' win rates, every component a fixed level set; allowed levels only):
    1 Klassisch rechts   old dev levels (test series, handmade8 dev except doppelgabel), validation v9 tiers 8-12,
                         v10 probes of classic skills
    2 Pruefung           the exam, 256 attempts
    3 Lange Level        guard levels (val + val_plus), validation "lang", v10 probe "lang", v13 "lang"
    4 Gabeln/Sackgassen  practice probes (sackgasse, gabel, lange_sackgasse), v10 probe "koeder", dev levels
                         doppelgabel / gabel_drei / kreuzung
    5 Kanaele/Umkehren   v10 probes kanal / umkehren, practice kanal*, dev level serpentine
    6 Links/Spiegel      v10 probe truhe_links, practice truhe_links_kurz, mirrored validation levels, spiegelweg
    7 Schwere Spruenge   v13 probes "spruenge" (generator v11)
    8 Neue Strukturen    v13 probes "strukturen" (generator v11)
Generalist value = mean of the 8 categories. Test groups are never part of it.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "runs/phase12"
CATS = ["1 Klassisch rechts", "2 Prüfung", "3 Lange Level", "4 Gabeln/Sackgassen", "5 Kanäle/Umkehren",
        "6 Links/Spiegel", "7 Schwere Sprünge", "8 Neue Strukturen"]
CLASSIC_PROBES = ("hohe_steine", "gegner_treppe", "decke", "luftstart", "gegner_entgegen", "gegner_dicht", "mario",
                  "truhe_abgrund")
VAL_SEED = 3_000_000_000
N_VAL = 12


def _file(path, needs_path=False):
    from jumpnrun.core.level import Level

    lv = Level.from_file(ROOT / path)
    lv.needs_path = needs_path or lv.goal_x < lv.spawn[0]
    return lv


def _probes(path, skills=None):
    from jumpnrun.rl.milestones10 import _probe_levels

    p = ROOT / path
    if not p.exists():
        return []
    out = [lv for s, lv in _probe_levels(p) if skills is None or s in skills]
    for lv in out:
        lv.needs_path = True
    return out


def components():
    """{component: (category index, [levels], attempts per level)} - deterministic."""

    from jumpnrun.levelgen import generator as G
    from jumpnrun.levelgen.distmap import DistanceMap
    from jumpnrun.levelgen.skills import LongSource, make_skill_level, mirror_level
    from jumpnrun.rl import milestones9 as m9
    from jumpnrun.rl.milestones10 import guard_split

    dev = {n: lv for n, lv, _ in m9.dev_levels()}
    for n in ("hand9_gabel_drei", "hand9_kreuzung", "hand9_serpentine", "hand9_spiegelweg"):
        dev[n].needs_path = True
    v10 = m9.probe_levels()
    comp = {}
    comp["dev_klassisch"] = (0, [lv for n, lv in dev.items() if n.startswith("serie_")
                                 or n in ("hand_abgrund", "hand_hoehlendach", "hand_lange_tour")], 8)
    comp["val_v9_t8-12"] = (0, [G.generate(t, VAL_SEED + 1000 * t + i) for t in range(8, 13) for i in range(N_VAL // 2)], 1)
    comp["proben_klassisch"] = (0, [lv for s, lv in v10 if s in CLASSIC_PROBES][:96], 1)
    comp["pruefung"] = (1, [dev["pruefung"]], 256)
    g = guard_split()
    comp["waechter_plus"] = (2, [_file(f"levels/handmade10/{n}.txt") for n in g["val"] + g["val_plus"]], 8)
    rng = random.Random("val12:lang")
    longs = [LongSource().make(rng) for _ in range(N_VAL)]
    comp["val_lang"] = (2, longs, 1)
    comp["probe_lang"] = (2, [lv for s, lv in v10 if s == "lang"], 1)
    comp["v13_lang"] = (2, [lv for lv, s in _v13() if s == "lang"], 1)
    comp["uebung_gabeln"] = (3, [make_skill_level(k, 2, f"val12:{k}:{i}") for k in
                                 ("sackgasse_runter", "gabel_umkehren", "gabel_oben", "lange_sackgasse")
                                 for i in range(N_VAL // 2)], 1)
    comp["probe_koeder"] = (3, [lv for s, lv in v10 if s == "koeder"], 1)
    comp["dev_gabeln"] = (3, [dev["hand_doppelgabel"], dev["hand9_gabel_drei"], dev["hand9_kreuzung"]], 8)
    comp["probe_kanal_umkehren"] = (4, [lv for s, lv in v10 if s in ("kanal", "umkehren")], 1)
    comp["uebung_kanal"] = (4, [make_skill_level(k, 2, f"val12:{k}:{i}") for k in ("kanal_ende", "kanal2", "kanal3")
                                for i in range(N_VAL // 2)], 1)
    comp["dev_serpentine"] = (4, [dev["hand9_serpentine"]], 8)
    comp["probe_truhe_links"] = (5, [lv for s, lv in v10 if s == "truhe_links"], 1)
    comp["uebung_truhe_links"] = (5, [make_skill_level("truhe_links_kurz", 2, f"val12:tl:{i}") for i in range(N_VAL)], 1)
    mirrored, i = [], 0
    while len(mirrored) < N_VAL:
        m = mirror_level(G.generate(4 + i % 9, VAL_SEED + 90_000 + i))
        i += 1
        if DistanceMap(m).reachable:
            mirrored.append(m)
    comp["val_gespiegelt"] = (5, mirrored, 1)
    comp["dev_spiegelweg"] = (5, [dev["hand9_spiegelweg"]], 8)
    comp["v13_spruenge"] = (6, [lv for lv, s in _v13() if s == "spruenge"], 2)
    comp["v13_strukturen"] = (7, [lv for lv, s in _v13() if s == "strukturen"], 2)
    return comp


def _v13():
    from jumpnrun.core.level import Level

    p = ROOT / "levels/probes/v13_hard.json"
    if not p.exists():
        return []
    out = []
    for item in json.loads(p.read_text())["levels"]:
        lv = Level.from_text(item["text"], name=item["name"])
        lv.needs_path = True
        out.append((lv, item["skill"]))
    return out


def _eval_component(args):
    import torch

    from jumpnrun.rl.evaluate import evaluate_levels
    from jumpnrun.rl.modelinfo import load_model

    path, name, seed, *det = args
    torch.set_num_threads(1)
    cat, levels, n = components()[name]
    np.random.seed(seed)
    torch.manual_seed(seed)
    res = evaluate_levels(load_model(path), levels * n, deterministic=bool(det and det[0])) if levels else []
    return name, {"kat": cat, "won": sum(int(r["won"]) for r in res), "of": len(res),
                  "fortschritt": round(float(np.mean([r["progress"] for r in res])), 3) if res else 0.0}


def summarize(comp: dict) -> dict:
    cats = []
    for k in range(len(CATS)):
        rates = [c["won"] / c["of"] for c in comp.values() if c["kat"] == k and c["of"]]
        cats.append(round(float(np.mean(rates)), 4) if rates else 0.0)
    return {"kategorien": cats, "generalist": round(float(np.mean(cats)), 4), "komponenten": comp}


def evaluate(path, seed: int = 0, procs: int = 1, deterministic: bool = False) -> dict:
    """Stochastic (sampled actions) by default - the scorecard rule; deterministic=True only for diagnosis."""

    names = list(components())
    jobs = [(str(path), n, seed, deterministic) for n in names]
    if procs > 1:
        from multiprocessing import Pool

        with Pool(procs) as pool:
            comp = dict(pool.map(_eval_component, jobs, chunksize=1))
    else:
        comp = dict(_eval_component(j) for j in jobs)
    return summarize(comp)


# ----------------------------------------------------------------------------------------------- picture
REF_MODELS = {"p8": "P8", "phase11": "Phase 11", "neustart": "Neustart", "lehrer10": "Phase-10-Lehrer"}


def references() -> dict:
    out = {}
    for tag in REF_MODELS:
        p = OUT / f"score_{tag}.json"
        if p.exists():
            out[tag] = json.loads(p.read_text())
    return out


def picture(current: dict, label: str, history=None, shadow=None, out=OUT / "scorecard.png", note: str = ""):
    """current: summarize() result; history: [(Mio. steps, generalist, klassisch)]; shadow: Neustart dev_alt curve
    [(Mio. steps, value)] as the comparison line at the same step count."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    refs = references()
    ink, ink2, grid, surface = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    green, yellow, red = "#2e8540", "#e0a800", "#c0392b"
    best = [max((r["kategorien"][k] for r in refs.values()), default=0.0) for k in range(len(CATS))]
    best_who = [max(refs, key=lambda t: refs[t]["kategorien"][k]) if refs else "" for k in range(len(CATS))]
    p8 = refs.get("p8", {}).get("kategorien")
    fig = plt.figure(figsize=(15, 9), facecolor=surface)
    ax = fig.add_axes([0.06, 0.42, 0.9, 0.48], facecolor=surface)
    vals = current["kategorien"]
    colors = [green if v > b + 0.05 else yellow if v >= b - 0.05 else red for v, b in zip(vals, best)]
    x = np.arange(len(CATS))
    ax.bar(x, [100 * v for v in vals], color=colors, width=0.62, zorder=2)
    for i, (v, b, who) in enumerate(zip(vals, best, best_who)):
        ax.plot([i - 0.36, i + 0.36], [100 * b, 100 * b], color=ink, linewidth=2.2, zorder=3)
        ax.text(i, 100 * v + 1.5, f"{100 * v:.0f} %", ha="center", va="bottom", fontsize=12, fontweight="bold",
                color=ink, zorder=4)
        if who:
            ax.text(i + 0.38, 100 * b, f"bisher\nbestes: {REF_MODELS[who]}", fontsize=7, color=ink2, va="center")
        if p8:
            ax.plot([i - 0.36, i + 0.36], [100 * p8[i]] * 2, color=ink2, linewidth=1, linestyle="--", zorder=3)
    ax.set_xticks(x, [c.replace(" ", "\n", 1) for c in CATS], fontsize=10)
    ax.set_ylim(0, 105)
    ax.set_ylabel("gewonnen in %")
    ax.grid(axis="y", color=grid)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.set_title(f"{label}  ·  Balken: grün = besser als das bisher beste Modell (+5 Pp), gelb = gleich (±5), "
                 f"rot = schlechter  ·  schwarzer Strich = bisher bestes, gestrichelt = P8", fontsize=10, loc="left",
                 color=ink2)
    fig.text(0.06, 0.95, f"Generalist-Wert {100 * current['generalist']:.1f} %", fontsize=26, fontweight="bold",
             color=ink)
    best_g = max((r["generalist"] for r in refs.values()), default=0.0)
    if refs:
        who = max(refs, key=lambda t: refs[t]["generalist"])
        fig.text(0.42, 0.955, f"(bisher bestes Modell: {REF_MODELS[who]} {100 * best_g:.1f} %, "
                 f"P8 {100 * refs.get('p8', {'generalist': 0})['generalist']:.1f} %)", fontsize=13, color=ink2)
    ax2 = fig.add_axes([0.06, 0.07, 0.55, 0.26], facecolor=surface)
    if history:
        h = sorted(history)
        ax2.plot([a for a, _, _ in h], [100 * g for _, g, _ in h], "o-", color="#2a78d6", linewidth=2.5,
                 label="Generalist-Wert (Phase 12)")
        ax2.plot([a for a, _, _ in h], [100 * k for _, _, k in h], "s--", color="#2a78d6", linewidth=1.2,
                 label="alte Dev-Level dev_alt (Phase 12)")
    if shadow:
        ax2.plot([a for a, _ in shadow], [100 * v for _, v in shadow], color="#9a9a9a", linewidth=4, alpha=0.5,
                 label="Neustart: alte Dev-Level beim gleichen Schrittstand")
    ax2.axhline(100 * best_g, color=ink, linewidth=1, linestyle=":", label="bisher bester Generalist-Wert")
    ax2.set_xlabel("Mio. Schritte")
    ax2.set_ylabel("%")
    ax2.grid(axis="y", color=grid)
    ax2.legend(frameon=False, fontsize=8, loc="lower right")
    for s in ("top", "right"):
        ax2.spines[s].set_visible(False)
    fig.text(0.65, 0.31, note, fontsize=9.5, color=ink2, va="top", wrap=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100)
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval")
    e.add_argument("model")
    e.add_argument("--tag", required=True)
    e.add_argument("--procs", type=int, default=1)
    e.add_argument("--seed", type=int, default=0)
    e.add_argument("--det", action="store_true", help="diagnosis only: always the most likely action")
    b = sub.add_parser("bild")
    b.add_argument("--tag", help="a stored score_<tag>.json")
    args = parser.parse_args()
    if args.cmd == "eval":
        res = evaluate(ROOT / args.model, args.seed, args.procs, deterministic=args.det)
        res["modell"] = args.model
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"score_{args.tag}.json").write_text(json.dumps(res, indent=1))
        print(args.tag, f"Generalist {res['generalist']:.1%}",
              " | ".join(f"{c}: {v:.0%}" for c, v in zip(CATS, res["kategorien"])))
    else:
        cur = json.loads((OUT / f"score_{args.tag}.json").read_text())
        print(picture(cur, REF_MODELS.get(args.tag, args.tag), out=OUT / f"scorecard_{args.tag}.png"))


if __name__ == "__main__":
    main()
