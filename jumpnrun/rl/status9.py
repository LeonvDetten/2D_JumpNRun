"""Phase 9 dashboard: the two arms of the current round side by side (as status8, plus old/new dev levels).

    python3 -m jumpnrun.rl.status9              # -> runs/phase9/status.png + short text

Panels: dev mean (EMA, 95 % band; raw dotted) with the round's start value and decision point, exam wins,
test group H + protection validation, capability probes (latest EMA), and what the training actually played
(share of fresh / stored / replayed / augmented episodes - proof that a data change arrives).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from jumpnrun.rl.autopilot9 import JUDGE_STEPS, ROOT, load_state, milestones, run_dir

INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
ARM_COLOR = {"neu": "#2a78d6", "kontrolle": "#eb6834"}
ARM_LABEL = {"neu": "neu", "kontrolle": "Kontrolle"}


def series(run: Path, kind: str):
    out = []
    for key, r in milestones(run).items():
        steps, k = key.split(":")
        if k == kind:
            out.append((int(steps), r))
    return sorted(out, key=lambda x: x[0])


def provenance(run: Path, last: int = 3000):
    path = run / "episodes.jsonl"
    if not path.exists():
        return Counter(), 0
    lines = path.read_text().splitlines()[-last:]
    c = Counter()
    for line in lines:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        c[e.get("source") or "?"] += 1
        if e.get("aug"):
            c["augmentiert"] += 1
    return c, len(lines)


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    state = load_state()
    rnd = state["round"]
    info = state["rounds"].get(str(rnd), {})
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.titlesize": 11, "axes.titleweight": "bold",
                         "axes.titlecolor": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    fig, axes = plt.subplots(2, 3, figsize=(16, 8.4))
    for ax in axes.flat:
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    lines = []
    start = info.get("start_steps", 0)
    for arm in ("neu", "kontrolle"):
        run = run_dir(rnd, arm)
        color = ARM_COLOR[arm]
        ema = series(run, "ema")
        raw = series(run, "raw")
        if ema:
            xs = [(s - start) / 1e6 for s, _ in ema]
            m = [100 * r["dev_mean"][0] for _, r in ema]
            lo = [100 * r["dev_mean"][1] for _, r in ema]
            hi = [100 * r["dev_mean"][2] for _, r in ema]
            axes[0, 0].plot(xs, m, color=color, linewidth=2, label=f"{ARM_LABEL[arm]} (EMA)")
            axes[0, 0].fill_between(xs, lo, hi, color=color, alpha=0.12)
            alt = [100 * r["dev_alt"][0] for _, r in ema]
            neu = [100 * r["dev_neu"][0] for _, r in ema]
            axes[0, 1].plot(xs, alt, color=color, linewidth=2, label=f"{ARM_LABEL[arm]}: alt (11)")
            axes[0, 1].plot(xs, neu, "--", color=color, linewidth=2, label=f"{ARM_LABEL[arm]}: neu (4)")
            th = [100 * r["test"]["won"] / r["test"]["of"] for _, r in ema if "test" in r]
            sc = [100 * r["schutz"]["won"] / r["schutz"]["of"] for _, r in ema if "schutz" in r]
            axes[0, 2].plot(xs[:len(th)], th, color=color, linewidth=2, label=f"{ARM_LABEL[arm]}: Test H")
            axes[0, 2].plot(xs[:len(sc)], sc, "--", color=color, linewidth=1.5, label=f"{ARM_LABEL[arm]}: Schutz")
            last = ema[-1][1]
            if "proben" in last:
                skills = list(last["proben"])
                y = np.arange(len(skills))
                off = 0.2 if arm == "neu" else -0.2
                axes[1, 0].barh(y + off, [100 * last["proben"][s]["won"] / last["proben"][s]["of"] for s in skills],
                                height=0.38, color=color, label=ARM_LABEL[arm])
                axes[1, 0].set_yticks(y, skills)
            lines.append(f"{ARM_LABEL[arm]}: {(ema[-1][0] - start) / 1e6:.1f} Mio. Schritte, Dev-Mittel "
                         f"{last['dev_mean'][0]:.1%} (alt {last['dev_alt'][0]:.0%}, neu {last['dev_neu'][0]:.0%}), "
                         f"Prüfung {last['dev']['pruefung']['won']}/{last['dev']['pruefung']['of']}")
        if raw:
            axes[0, 0].plot([(s - start) / 1e6 for s, _ in raw], [100 * r["dev_mean"][0] for _, r in raw], ":",
                            color=color, linewidth=1.2, label=f"{ARM_LABEL[arm]} (roh)")
        prov, n = provenance(run)
        if n:
            keys = ["fresh", "pool", "plr", "midstart", "handmade", "augmentiert"]
            off = 0.2 if arm == "neu" else -0.2
            axes[1, 1].barh(np.arange(len(keys)) + off, [100 * prov.get(k, 0) / n for k in keys], height=0.38,
                            color=color, label=ARM_LABEL[arm])
            axes[1, 1].set_yticks(np.arange(len(keys)), ["frisch", "gespeichert", "PLR", "Mitte-Start",
                                                         "handgebaut", "augmentiert"])
    if info.get("baseline") is not None:
        axes[0, 0].axhline(100 * info["baseline"], color=INK2, linewidth=1, linestyle="-.", label="Start")
    for ax in (axes[0, 0], axes[0, 1], axes[0, 2]):
        ax.axvline(JUDGE_STEPS / 1e6, color=INK2, linewidth=1, linestyle=":")
        ax.set_xlabel("Mio. Schritte seit Rundenstart")
        ax.legend(frameon=False, fontsize=8, loc="lower left")
    axes[0, 0].set_title("Dev-Mittel (15 Level) in %", loc="left")
    axes[0, 1].set_title("Dev alt (Phase-8-Level) und neu (Phase-9-Level) in %", loc="left")
    axes[0, 2].set_title("Test H und Schutz-Validierung in %", loc="left")
    axes[1, 0].set_title("Fähigkeits-Proben (letzter EMA-Stand) in %", loc="left")
    axes[1, 0].legend(frameon=False, fontsize=8)
    axes[1, 1].set_title("Was das Training spielt (letzte 3000 Episoden) in %", loc="left")
    axes[1, 1].legend(frameon=False, fontsize=8)
    axes[1, 2].axis("off")
    hours = 0.0
    if state.get("started"):
        import time

        hours = (time.time() - state["started"]) / 3600
    text = [f"Runde {rnd} – Entscheidung nach {JUDGE_STEPS / 1e6:.0f} Mio. Schritten je Arm",
            f"Phase-9-Zeit: {hours:.1f} h von 48 h"] + lines + ["", "Letzte Autopilot-Einträge:"] + \
        [l[:90] for l in state.get("log", [])[-6:]]
    axes[1, 2].text(0, 1, "\n".join(text), va="top", ha="left", fontsize=8.5, color=INK2, transform=axes[1, 2].transAxes)
    fig.suptitle(f"Phase 9 · Runde {rnd}", x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = ROOT / "runs/phase9/status.png"
    fig.savefig(out, dpi=100)
    plt.close(fig)
    print("\n".join(text))
    print("Bild:", out)


if __name__ == "__main__":
    main()
