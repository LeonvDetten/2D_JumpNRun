"""Phase 13 verdict picture: categories at T = 0.3 (paired, seeds 1+2) for stand 0, the candidate (+2 M) and the
left alternative (+10 M EMA2), plus the left / fork extras. -> docs/lernen/medien/phase13/urteil.png"""

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

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
d = json.loads((ROOT / "docs/lernen/daten/phase13_urteil.json").read_text())["modelle"]
SEL = (("stand0", "Stand 0 (Phase-12-Kandidat)", BLUE), ("p13_46", "Phase 13 · +2 Mio. (Kandidat)", ORANGE),
       ("p13_54e2", "Phase 13 · +10 Mio. EMA2 (Links-Alternative)", AQUA))


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
gs = fig.add_gridspec(2, 1, height_ratios=[1.2, 1], hspace=0.45)
ax = fig.add_subplot(gs[0])
style(ax, "gewonnen in % (T = 0,3)")
labels = [c.split(" ", 1)[1] for c in S.CATS]
x = np.arange(len(labels))
w = 0.27
for j, (t, name, color) in enumerate(SEL):
    vals = [100 * v for v in d[t]["0.3"]["kategorien"]]
    g = 100 * d[t]["0.3"]["generalist"]
    ax.bar(x + (j - 1) * (w + 0.01), vals, w, color=color, label=f"{name}: Generalist {g:.1f} %")
    for i, v in enumerate(vals):
        ax.text(x[i] + (j - 1) * (w + 0.01), v + 1.2, f"{v:.0f}", ha="center", fontsize=8, color=INK)
ax.set_xticks(x, labels, fontsize=10, color=INK)
ax.set_ylim(0, 108)
ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, ncol=1, fontsize=10)
ax.set_title("Je Kategorie (gepaart, frische Seeds 1 + 2)", loc="left", fontsize=12, color=INK, pad=62)

ax = fig.add_subplot(gs[1])
style(ax, "gewonnen in %")
items = (("spiegelweg", "spiegelweg\n(nach links, nie trainiert)"), ("hand9_gabel_drei", "gabel_drei\n(Dev-Gabel)"),
         ("hand9_kreuzung", "kreuzung\n(Dev-Gabel)"), ("hand_doppelgabel", "doppelgabel\n(Dev-Gabel)"),
         ("links_spruenge", "Sprung-Proben gespiegelt\n(nach links, nie trainiert)"))
x2 = np.arange(len(items))
for j, (t, name, color) in enumerate(SEL):
    e = d[t]["extras"]
    vals = [100 * e[k]["won"] / e[k]["of"] for k, _ in items]
    ax.bar(x2 + (j - 1) * (w + 0.01), vals, w, color=color)
    for i, (k, _) in enumerate(items):
        ax.text(x2[i] + (j - 1) * (w + 0.01), vals[i] + 1.5, f"{e[k]['won']}/{e[k]['of']}", ha="center", fontsize=8,
                color=INK)
ax.set_xticks(x2, [n for _, n in items], fontsize=9, color=INK)
ax.set_ylim(0, 110)
ax.set_title("Einzelne schwere Level (T = 0,3, Seeds 1 + 2)", loc="left", fontsize=12, color=INK)
fig.suptitle("Phase 13 · Urteil: Links-Präzision und Nachschärfen", x=0.06, y=1.07, ha="left", fontsize=16, color=INK,
             fontweight="bold")
out = ROOT / "docs/lernen/medien/phase13/urteil.png"
fig.savefig(out, dpi=100, facecolor=SURFACE, bbox_inches="tight")
print(out)
