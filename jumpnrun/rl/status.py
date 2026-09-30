"""Status report for a running (or finished) training run: one dashboard image + a short verdict.

    python -m jumpnrun.rl.status --run runs/phase6 --png status.png

The image has four panels:
    1 exam: won attempts per milestone (original + defused)
    2 validation v2 / v3 and test series in percent
    3 where the exam attempts ended at the latest milestone
    4 training win rate over time, per group of tiers

The verdict is a simple, deliberately conservative rule set that says whether
waiting longer is likely to help or whether something has to change:
    progress  a new best (validation or exam) within the last 3 milestones
    plateau   no new best for >= 5 milestones and training win rate flat
    regress   recent milestones clearly below the best one
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

SECTIONS = (("start_gegnerregen", "Start / Gegnerregen"), ("gabelung_oben", "Gabelung"),
            ("trittsteine", "Trittsteine"), ("diagonalen", "Diagonalen"), ("ziel", "Ziel / Tiefsprung"))
GROUPS = (("Stufen 0–5", range(0, 6)), ("Stufen 6–9", range(6, 10)), ("Stufen 10–11", range(10, 12)),
          ("Start mitten im Level", (-2,)))
# reference palette (dataviz skill), light mode
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7")
BAD = "#e34948"


def load(run: Path):
    milestones = json.loads((run / "milestones.json").read_text()) if (run / "milestones.json").exists() else {}
    rows = []
    for k in sorted(milestones, key=int):
        v = milestones[k]
        rows.append(dict(
            steps=int(k), v2=v["validierung_v2"]["won"], v2n=v["validierung_v2"]["of"],
            v3=v["validierung_v3"]["won"], v3n=v["validierung_v3"]["of"],
            ts=sum(s["won"] for s in v["test_serie"].values()), tsn=sum(s["of"] for s in v["test_serie"].values()),
            ex=v["pruefung"]["original"]["won"], exe=v["pruefung"]["entschaerft"]["won"],
            exn=v["pruefung"]["original"]["of"], ends=v["pruefung"]["original"]["ends"]))
    curve = defaultdict(lambda: defaultdict(list))
    path = run / "episodes.jsonl"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for name, tiers in GROUPS:
                    if e["tier"] in tiers:
                        curve[name][e["timesteps"] // 500_000].append(e["won"])
    seconds = float((run / "seconds_used").read_text()) if (run / "seconds_used").exists() else 0.0
    return rows, curve, seconds


def verdict(rows, curve):
    """Returns (label, list of explanation lines)."""

    if len(rows) < 4:
        return "zu früh", ["Weniger als 4 Meilensteine – noch keine belastbare Aussage."]
    val = [r["v2"] + r["v3"] for r in rows]
    ex = [r["ex"] + r["exe"] for r in rows]
    since_val = len(rows) - 1 - max(i for i, v in enumerate(val) if v == max(val))
    since_ex = len(rows) - 1 - max(i for i, v in enumerate(ex) if v == max(ex))
    lines = [f"Beste Validierung vor {since_val} Meilensteinen ({max(val)} von {rows[0]['v2n'] + rows[0]['v3n']}), "
             f"beste Prüfung vor {since_ex} Meilensteinen ({max(ex)} von {2 * rows[0]['exn']})."]
    # training trend: last 3M steps vs the 3M before, over all tier groups
    trend = []
    for name, _ in GROUPS:
        buckets = curve.get(name, {})
        keys = sorted(buckets)
        if len(keys) >= 12:
            recent = np.mean([w for k in keys[-6:] for w in buckets[k]])
            before = np.mean([w for k in keys[-12:-6] for w in buckets[k]])
            trend.append(recent - before)
    flat = bool(trend) and max(abs(t) for t in trend) < 0.03
    if trend:
        lines.append("Trainings-Erfolg letzte 3 Mio. gegenüber den 3 Mio. davor: "
                     + ", ".join(f"{name} {t:+.0%}" for (name, _), t in zip(GROUPS, trend)))
    recent_ends = defaultdict(int)
    for r in rows[-4:]:
        for key, n in r["ends"].items():
            recent_ends[key] += n
    if recent_ends:
        key = max(recent_ends, key=recent_ends.get)
        share = recent_ends[key] / max(1, sum(recent_ends.values()))
        lines.append(f"Engpass auf dem Prüfungslevel: {dict(SECTIONS)[key]} ({share:.0%} der gescheiterten Versuche, letzte 4 Meilensteine).")
    recent_val = np.mean(val[-3:])
    if min(since_val, since_ex) <= 2:
        return "Fortschritt", lines + ["Weiterlaufen lassen lohnt sich: Es gibt noch neue Bestwerte."]
    if recent_val < max(val) - 0.08 * (rows[0]["v2n"] + rows[0]["v3n"]):
        return "Rückschritt", lines + ["Die letzten Meilensteine liegen deutlich unter dem Bestwert. "
                                       "Weiterlaufen bringt wahrscheinlich wenig; Lernrate oder Datenmischung prüfen."]
    if min(since_val, since_ex) >= 5 and (flat or not trend):
        return "Plateau", lines + ["Seit 5+ Meilensteinen kein Bestwert und der Trainings-Erfolg ist flach. "
                                   "Längeres Warten bringt vermutlich wenig – Eingriff überlegen (Daten, Netz, Belohnung)."]
    return "stagniert leicht", lines + ["Kein neuer Bestwert, aber noch Bewegung im Training. Noch 1–2 Meilensteine abwarten."]


def draw(rows, curve, seconds, label, png):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.titlesize": 11, "axes.titleweight": "bold",
                         "axes.titlecolor": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.6))
    steps = np.array([r["steps"] for r in rows]) / 1e6
    for ax in axes.flat:
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)

    ax = axes[0, 0]
    if rows:
        ax.bar(steps - 0.2, [r["ex"] for r in rows], width=0.4, color=SERIES[0], label="original")
        ax.bar(steps + 0.2, [r["exe"] for r in rows], width=0.4, color=SERIES[1], label="entschärft")
        ax.set_ylim(0, max(8, max(max(r["ex"], r["exe"]) for r in rows) + 2))
        ax.legend(frameon=False, loc="upper left")
    ax.set_title(f"Prüfung: gewonnene Versuche (von {rows[0]['exn'] if rows else 32})", loc="left")
    ax.set_xlabel("Mio. Schritte")

    ax = axes[0, 1]
    for (key, n, name), color in zip((("v2", "v2n", "Validierung Stufen 4–9"), ("v3", "v3n", "Validierung lang"),
                                      ("ts", "tsn", "Test-Serie")), SERIES):
        if rows:
            ys = [100 * r[key] / r[n] for r in rows]
            ax.plot(steps, ys, color=color, linewidth=2, label=name)
            ax.plot(steps[-1], ys[-1], "o", color=color, markersize=6)
    ax.set_ylim(0, 100)
    ax.set_title("Unbekannte Level: gewonnen in %", loc="left")
    ax.set_xlabel("Mio. Schritte")
    ax.legend(frameon=False, loc="lower right")

    ax = axes[1, 0]
    if rows:
        last = rows[-1]
        names = [name for _, name in SECTIONS] + ["im Ziel"]
        values = [last["ends"].get(key, 0) for key, _ in SECTIONS] + [last["ex"]]
        colors = [BAD] * len(SECTIONS) + [SERIES[2]]
        y = np.arange(len(names))[::-1]
        ax.barh(y, values, color=colors, height=0.6)
        ax.set_yticks(y, names)
        for yy, v in zip(y, values):
            ax.text(v + 0.3, yy, str(v), va="center", color=INK2)
        ax.set_xlim(0, last["exn"])
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.grid(axis="y", visible=False)
        ax.set_title(f"Wo die Versuche enden ({last['steps'] / 1e6:.0f} Mio.)", loc="left")

    ax = axes[1, 1]
    for (name, _), color in zip(GROUPS, SERIES):
        buckets = curve.get(name, {})
        keys = sorted(buckets)
        if keys:
            xs = [(k + 1) * 0.5 for k in keys]
            ys = [100 * np.mean(buckets[k]) for k in keys]
            ax.plot(xs, ys, color=color, linewidth=2, label=name)
    ax.set_ylim(0, 100)
    ax.set_title("Training: gewonnene Episoden in %", loc="left")
    ax.set_xlabel("Mio. Schritte")
    ax.legend(frameon=False, loc="lower right")

    hours = seconds / 3600
    fig.suptitle(f"Stand: {rows[-1]['steps'] / 1e6:.1f} Mio. Schritte · {hours:.1f} h Training · Einschätzung: {label}"
                 if rows else "Noch keine Meilensteine", x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(png, dpi=110)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dashboard image + verdict for a training run.")
    parser.add_argument("--run", required=True)
    parser.add_argument("--png", default=None, help="output image (default: <run>/status.png)")
    args = parser.parse_args()
    run = Path(args.run)
    rows, curve, seconds = load(run)
    label, lines = verdict(rows, curve)
    png = args.png or str(run / "status.png")
    draw(rows, curve, seconds, label, png)
    print(f"Einschätzung: {label}")
    for line in lines:
        print(" - " + line)
    print(f"Bild: {png}")


if __name__ == "__main__":
    main()
