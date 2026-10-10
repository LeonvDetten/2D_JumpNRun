"""Phase 12: how much of the gap is 'unsure play'? Generalist value and exam vs. sampling temperature
(1 = the policy as trained, lower = sharper choice, 0 = deterministic), from runs/phase12/diagnose_*_T*.json.

    python3 scripts/temperatur12.py   # -> docs/lernen/medien/phase12/temperatur.png
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from jumpnrun.rl import scorecard12 as S  # noqa: E402

D = ROOT / "runs/phase12"
BLUE, ORANGE, INK, INK2, GRID, SURFACE = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
TEMPS = [1.0, 0.7, 0.5, 0.3, 0.0]


def load(tag, t):
    if t == 0.0:
        d = json.loads((D / f"diagnose_{tag}.json").read_text())
        return d["generalist_deterministisch"], d["kategorien"]["deterministisch"]
    name = f"diagnose_{tag}.json" if t == 1.0 else f"diagnose_{tag}_T{t}.json"
    d = json.loads((D / name).read_text())
    return d["generalist_zufaellig"], d["kategorien"]["zufaellig"]


def style(ax, ylabel):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_ylabel(ylabel, color=INK2)


fig = plt.figure(figsize=(15, 10), facecolor=SURFACE)
gs = fig.add_gridspec(2, 2, hspace=0.45, wspace=0.2)
xt = np.arange(len(TEMPS))
xl = ["1,0\n(wie trainiert)", "0,7", "0,5", "0,3", "0\n(deterministisch)"]
for k, (title, pick) in enumerate((("Generalist-Wert", lambda g, c: g), ("Prüfung (256 Versuche)", lambda g, c: c[1]["rate"]))):
    ax = fig.add_subplot(gs[0, k])
    style(ax, "%")
    for tag, name, color in (("p12", "Phase 12", BLUE), ("p8", "P8", ORANGE)):
        ys = [100 * pick(*load(tag, t)) for t in TEMPS]
        ax.plot(xt, ys, color=color, linewidth=2, marker="o", markersize=8, label=name)
        for x, y in zip(xt, ys):  # P8 labels below the line, so equal values do not overlap
            ax.text(x, y + 2.5 if tag == "p12" else y - 6, f"{y:.0f}", ha="center", fontsize=9, color=color)
    ax.set_xticks(xt, xl, fontsize=9, color=INK)
    ax.set_xlabel("Temperatur beim Spielen", color=INK2)
    ax.set_ylim(0, 108)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, ncol=2, fontsize=10)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=26)
    if k == 1:
        ax.annotate("deterministisch: ein einziger fester Ablauf", (4, 100), xytext=(2.3, 30), fontsize=8, color=INK2,
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))

ax = fig.add_subplot(gs[1, :])
style(ax, "gewonnen in %")
labels = [c.split(" ", 1)[1] for c in S.CATS]
x = np.arange(len(labels))
w = 0.38
a = [100 * c["rate"] for c in load("p12", 1.0)[1]]
b = [100 * c["rate"] for c in load("p12", 0.3)[1]]
ax.bar(x - w / 2 - 0.01, a, w, color=BLUE, label="Phase 12, Temperatur 1,0 (wie gemessen)")
ax.bar(x + w / 2 + 0.01, b, w, color=ORANGE, label="Phase 12, Temperatur 0,3 (geschärft)")
for i in range(len(x)):
    ax.text(x[i] - w / 2, a[i] + 1.5, f"{a[i]:.0f}", ha="center", fontsize=9, color=INK)
    ax.text(x[i] + w / 2, b[i] + 1.5, f"{b[i]:.0f}", ha="center", fontsize=9, color=INK)
ax.set_xticks(x, labels, fontsize=10, color=INK)
ax.set_ylim(0, 108)
ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, ncol=2, fontsize=10)
ax.set_title("Je Kategorie: wie trainiert vs. geschärft", loc="left", fontsize=12, color=INK, pad=26)
fig.suptitle("Phase 12 · geschärfte Wahl beim Spielen (Seed 1, gleiche Level für beide Modelle)", x=0.06, ha="left",
             fontsize=15, color=INK, fontweight="bold")
out = ROOT / "docs/lernen/medien/phase12/temperatur.png"
fig.savefig(out, dpi=100, facecolor=SURFACE, bbox_inches="tight")
print(out)
