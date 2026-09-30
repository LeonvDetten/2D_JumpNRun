"""Status report for running (or finished) training runs: one dashboard image + a short verdict per run.

    python -m jumpnrun.rl.status --run runs/phase7a --run runs/phase7b --png status.png

Panels (each run in its own colour; dashed = EMA copy of the weights):
    exam original won in %      test series won in %      validation won in %
    where exam attempts ended   training win rate run 1   training win rate run 2

The verdict is a simple, deliberately conservative rule set that says whether waiting longer is
likely to help or whether something has to change:
    Fortschritt   a clear new best (>= 2 validation levels or >= 3 exam wins) within the last 3 milestones
    Plateau       no clear new best for >= 5 milestones and training win rate flat
    Rückschritt   recent milestones clearly below the best one
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

SECTIONS = (("start_gegnerregen", "Start"), ("gabelung_oben", "Gabelung"), ("trittsteine", "Trittsteine"),
            ("diagonalen", "Diagonalen"), ("ziel", "Ziel"))
GROUPS = (("Stufen 0–5", range(0, 6)), ("Stufen 6–9", range(6, 10)), ("Stufen 10–12", range(10, 13)),
          ("Start mitten im Level", (-2,)), ("Rückspul-Start", (-3,)))
# reference palette (dataviz skill), light mode, fixed slot order
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4")
BAD = "#e34948"


def _row(steps: int, v: dict) -> dict:
    vals = [x for k, x in v.items() if k.startswith("validierung_")]
    return dict(steps=steps, val=sum(x["won"] for x in vals), valn=sum(x["of"] for x in vals),
                v2=v["validierung_v2"]["won"], v3=v["validierung_v3"]["won"],
                ts=sum(s["won"] for s in v["test_serie"].values()), tsn=sum(s["of"] for s in v["test_serie"].values()),
                ex=v["pruefung"]["original"]["won"], exe=v["pruefung"]["entschaerft"]["won"],
                exn=v["pruefung"]["original"]["of"], ends=v["pruefung"]["original"]["ends"])


def load(run: Path):
    milestones = json.loads((run / "milestones.json").read_text()) if (run / "milestones.json").exists() else {}
    rows = {"raw": [], "ema": []}
    for k, v in milestones.items():
        steps, kind = (k.split(":") + ["raw"])[:2]
        rows[kind].append(_row(int(steps), v))
    for kind in rows:
        rows[kind].sort(key=lambda r: r["steps"])
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
    """Returns (label, list of explanation lines). Raw and EMA count together (best per milestone)."""

    best_of = {}
    for r in rows["raw"] + rows["ema"]:
        cur = best_of.get(r["steps"])
        if cur is None or (r["val"] + r["ex"]) > (cur["val"] + cur["ex"]):
            best_of[r["steps"]] = r
    merged = [best_of[k] for k in sorted(best_of)]
    if len(merged) < 4:
        return "zu früh", ["Weniger als 4 Meilensteine – noch keine belastbare Aussage."]
    val = [r["val"] for r in merged]
    ex = [r["ex"] for r in merged]

    def since_clear_best(values, margin):
        best, since = values[0], 0
        for i, v in enumerate(values[1:], 1):
            if v >= best + margin:
                best, since = v, 0
            else:
                since += 1
                best = max(best, v)
        return since

    since_val, since_ex = since_clear_best(val, 2), since_clear_best(ex, 3)
    lines = [f"Letzter klarer Bestwert: Validierung vor {since_val}, Prüfung vor {since_ex} Meilensteinen "
             f"(Bestwerte {max(val)}/{merged[0]['valn']} bzw. {max(ex)}/{merged[0]['exn']})."]
    trend = []
    for name, _ in GROUPS:
        buckets = curve.get(name, {})
        keys = sorted(buckets)
        if len(keys) >= 12:
            recent = np.mean([w for k in keys[-6:] for w in buckets[k]])
            before = np.mean([w for k in keys[-12:-6] for w in buckets[k]])
            trend.append((name, recent - before))
    flat = bool(trend) and max(abs(t) for _, t in trend) < 0.03
    if trend:
        lines.append("Trainings-Erfolg letzte 3 Mio. gegenüber den 3 Mio. davor: "
                     + ", ".join(f"{name} {t:+.0%}" for name, t in trend))
    recent_ends = defaultdict(int)
    for r in merged[-4:]:
        for key, n in r["ends"].items():
            recent_ends[key] += n
    if recent_ends:
        key = max(recent_ends, key=recent_ends.get)
        share = recent_ends[key] / max(1, sum(recent_ends.values()))
        lines.append(f"Engpass auf dem Prüfungslevel: {dict(SECTIONS)[key]} ({share:.0%} der gescheiterten "
                     f"Versuche, letzte 4 Meilensteine).")
    if min(since_val, since_ex) <= 2:
        return "Fortschritt", lines
    if np.mean(val[-3:]) < max(val) - 0.08 * merged[0]["valn"]:
        return "Rückschritt", lines
    if min(since_val, since_ex) >= 5 and (flat or not trend):
        return "Plateau", lines
    return "stagniert leicht", lines


def draw(runs: dict, png: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.titlesize": 11, "axes.titleweight": "bold",
                         "axes.titlecolor": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    n_runs = len(runs)
    fig, axes = plt.subplots(2, 2 + n_runs, figsize=(5.2 * (2 + n_runs), 7.6), squeeze=False)
    for ax in axes.flat:
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    metrics = (("ex", "exn", "Prüfung original: gewonnen in %"), ("ts", "tsn", "Test-Serie: gewonnen in %"),
               ("val", "valn", "Validierung: gewonnen in %"))
    top = list(axes[0])
    for ax, (key, n, title) in zip(top, metrics):
        for (name, (rows, _, _)), color in zip(runs.items(), SERIES):
            for kind, style in (("raw", "-"), ("ema", "--")):
                rs = rows[kind]
                if rs:
                    xs = [r["steps"] / 1e6 for r in rs]
                    ys = [100 * r[key] / r[n] for r in rs]
                    ax.plot(xs, ys, style, color=color, linewidth=2, label=f"{name}{' EMA' if kind == 'ema' else ''}")
                    ax.plot(xs[-1], ys[-1], "o", color=color, markersize=6)
        ax.set_ylim(0, 100)
        ax.set_title(title, loc="left")
        ax.set_xlabel("Mio. Schritte")
        ax.legend(frameon=False, loc="upper left", fontsize=8)
    for ax in top[3:]:
        ax.axis("off")
    ax = axes[1, 0]
    width = 0.8 / max(1, n_runs)
    y = np.arange(len(SECTIONS) + 1)[::-1]
    for i, ((name, (rows, _, _)), color) in enumerate(zip(runs.items(), SERIES)):
        if rows["raw"]:
            last = rows["raw"][-1]
            values = [last["ends"].get(k, 0) for k, _ in SECTIONS] + [last["ex"]]
            ax.barh(y - i * width + 0.4 - width / 2, values, height=width * 0.9, color=color,
                    label=f"{name} ({last['steps'] / 1e6:.0f} Mio.)")
    ax.set_yticks(y, [name for _, name in SECTIONS] + ["im Ziel"])
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    ax.set_title("Wo die Prüfungsversuche enden", loc="left")
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    axes[1, 1].axis("off")
    lines = []
    for name, (rows, curve, seconds) in runs.items():
        label, why = verdict(rows, curve)
        lines.append(f"{name}: {label} · {seconds / 3600:.1f} h Training")
        lines += ["  " + w for w in why]
    axes[1, 1].text(0, 1, "\n".join(_wrap(l, 62) for l in lines), va="top", ha="left", fontsize=8.5, color=INK2,
                    transform=axes[1, 1].transAxes)
    for j, (name, (rows, curve, _)) in enumerate(runs.items()):
        ax = axes[1, 2 + j]
        for (group, _), color in zip(GROUPS, SERIES):
            buckets = curve.get(group, {})
            keys = sorted(buckets)
            if keys:
                ax.plot([(k + 1) * 0.5 for k in keys], [100 * np.mean(buckets[k]) for k in keys], color=color,
                        linewidth=2, label=group)
        ax.set_ylim(0, 100)
        ax.set_title(f"Training {name}: gewonnene Episoden in %", loc="left")
        ax.set_xlabel("Mio. Schritte")
        ax.legend(frameon=False, loc="lower right", fontsize=8)
    parts = []
    for name, (rows, _, seconds) in runs.items():
        newest = max((r["steps"] for r in rows["raw"]), default=0)
        parts.append(f"{name} {newest / 1e6:.1f} Mio. Schritte / {seconds / 3600:.1f} h")
    fig.suptitle("Stand: " + " · ".join(parts), x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(png, dpi=100)
    plt.close(fig)


def _wrap(text: str, width: int) -> str:
    import textwrap

    return "\n".join(textwrap.wrap(text, width, subsequent_indent="    ")) or text


def main() -> None:
    parser = argparse.ArgumentParser(description="Dashboard image + verdict for training runs.")
    parser.add_argument("--run", action="append", required=True)
    parser.add_argument("--name", action="append", help="display name per run (default: folder name)")
    parser.add_argument("--png", default=None, help="output image (default: <first run>/status.png)")
    args = parser.parse_args()
    names = args.name or [Path(r).name for r in args.run]
    runs = {name: load(Path(r)) for name, r in zip(names, args.run)}
    png = args.png or str(Path(args.run[0]) / "status.png")
    draw(runs, png)
    for name, (rows, curve, _) in runs.items():
        label, lines = verdict(rows, curve)
        print(f"{name}: Einschätzung {label}")
        for line in lines:
            print(" - " + line)
    print(f"Bild: {png}")


if __name__ == "__main__":
    main()
