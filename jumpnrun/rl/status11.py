"""Phase 11 dashboard: arm A (with mirrored levels) and arm B (without) side by side.

    python3 -m jumpnrun.rl.status11              # -> runs/phase11/status.png + short text

Panels: dev_alt (EMA solid, raw dotted) against start and P8; exam and doppelgabel; generalist value G and its
parts (voll measurements); mirrored levels (alt / long); shares of training steps per source; text.
"""

from __future__ import annotations

import json
import time
from collections import Counter

import numpy as np

from jumpnrun.rl import autopilot11 as A

INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COLORS = {"a": "#2a78d6", "b": "#eb6834"}
SOURCES = [("p8", "Phase 8"), ("skill", "Übung"), ("v10", "lange v10"), ("lang", "lang (2 Level)"),
           ("spiegel", "gespiegelt")]


def series(run: str, kind: str, full: bool = False):
    out = [(int(k.split(":")[0]), v) for k, v in A.milestones(run).items() if k.split(":")[1] == kind]
    if full:
        out = [(s, v) for s, v in out if v.get("size") == "voll"]
    return sorted(out, key=lambda x: x[0])


def step_shares(run: str, last: int = 4000):
    path = A.ROOT / run / "episodes.jsonl"
    if not path.exists():
        return Counter(), 0
    c = Counter()
    for line in path.read_text().splitlines()[-last:]:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        c[e.get("mix") or "p8"] += e["steps"]
    return c, sum(c.values())


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    state = A.load_state()
    start = A.start_steps()
    p8, lehrer = A.baseline("p8"), A.baseline("lehrer")
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.titlesize": 11, "axes.titleweight": "bold",
                         "axes.titlecolor": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    fig, axes = plt.subplots(2, 3, figsize=(16, 8.4))
    for ax in axes.flat:
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    x = lambda s: (s - start) / 1e6  # noqa: E731
    lines = []
    for name, run in A.arms().items():
        color = COLORS.get(name, INK2)
        label = {"a": "A (mit Spiegel)", "b": "B (ohne)"}.get(name, name)
        ema, raw = series(run, "ema"), series(run, "raw")
        full = sorted(series(run, "ema", True) + series(run, "ema2", True), key=lambda t: t[0])
        if ema:
            axes[0, 0].plot([x(s) for s, _ in ema], [100 * r["dev_alt"] for _, r in ema], "o-", color=color,
                            linewidth=2, label=f"{label} EMA")
            axes[0, 1].plot([x(s) for s, _ in ema], [100 * A.exam_rate(r) for _, r in ema], "o-", color=color,
                            linewidth=2, label=f"{label}: Prüfung")
            axes[0, 1].plot([x(s) for s, _ in ema], [100 * r["doppelgabel_rate"] for _, r in ema], "--",
                            color=color, linewidth=1.3, label=f"{label}: doppelgabel")
            last = ema[-1][1]
            p = last["dev"]["pruefung"]
            lines.append(f"{label}: {x(ema[-1][0]):+.1f} Mio., dev_alt {last['dev_alt']:.1%}, F {last['F']:.1%}, "
                         f"Prüfung {p['won']}/{p['of']}, doppelgabel {last['doppelgabel']['won']}/16")
        if raw:
            axes[0, 0].plot([x(s) for s, _ in raw], [100 * r["dev_alt"] for _, r in raw], ":", color=color,
                            linewidth=1.2, label=f"{label} roh")
        if full:
            xs = [x(s) for s, _ in full]
            axes[0, 2].plot(xs, [100 * r["G"] for _, r in full], "o-", color=color, linewidth=2, label=f"{label}: G")
            axes[0, 2].plot(xs, [100 * r["waechter_plus_rate"] for _, r in full], "s:", color=color, linewidth=1,
                            label=f"{label}: Wächter+")
            axes[1, 0].plot(xs, [100 * r["spiegel_alt_rate"] for _, r in full], "o-", color=color, linewidth=2,
                            label=f"{label}: gespiegelt alt")
            axes[1, 0].plot(xs, [100 * r["spiegel_lang_rate"] for _, r in full], "s--", color=color, linewidth=1.3,
                            label=f"{label}: gespiegelt lang")
            r = full[-1][1]
            lines.append(f"   voll {x(full[-1][0]):+.1f}: G {r['G']:.1%}, Spiegel {r['spiegel_rate']:.1%}, "
                         f"Wächter+ {r['waechter_plus_rate']:.1%}, Sackgasse {r['sackgasse_rate']:.1%}")
        shares, n = step_shares(run)
        if n:
            off = 0.2 if name == "a" else -0.2
            axes[1, 1].barh(np.arange(len(SOURCES)) + off, [100 * shares.get(k, 0) / n for k, _ in SOURCES],
                            height=0.38, color=color, label=label)
            axes[1, 1].set_yticks(np.arange(len(SOURCES)), [t for _, t in SOURCES])
    for base, label, style in ((lehrer, "Start (P10-Lehrer)", "-."), (p8, "P8", "--")):
        if base is None:
            continue
        axes[0, 0].axhline(100 * base["dev_alt"], color=INK2, linewidth=1, linestyle=style, label=label)
        axes[0, 1].axhline(100 * A.exam_rate(base), color=INK2, linewidth=1, linestyle=style, label=f"{label}: Prüfung")
        axes[0, 2].axhline(100 * base["G"], color=INK2, linewidth=1, linestyle=style, label=f"{label}: G")
        axes[1, 0].axhline(100 * base["spiegel_rate"], color=INK2, linewidth=1, linestyle=style, label=label)
    if p8 is not None:
        axes[0, 0].axhline(100 * (p8["dev_alt"] - 0.03), color="#b3261e", linewidth=0.8, linestyle=":",
                           label="Halte-Tor (P8 − 3 Pp)")
    titles = {(0, 0): "dev_alt (11 alte Dev-Level) in %", (0, 1): "Prüfung und doppelgabel in %",
              (0, 2): "Generalist-Wert G und Wächter-plus in %", (1, 0): "Gespiegelte Level (Truhe links) in %",
              (1, 1): "Anteile der Trainingsschritte (letzte 4000 Episoden) in %"}
    for (i, j), t in titles.items():
        axes[i, j].set_title(t, loc="left")
        axes[i, j].legend(frameon=False, fontsize=7.5, loc="best")
        if (i, j) != (1, 1):
            axes[i, j].set_xlabel("Mio. Schritte seit Phasenstart")
    axes[1, 2].axis("off")
    hours = (time.time() - state["started"]) / 3600
    text = [f"Phase 11 · {hours:.1f} h seit Start"] + lines
    if state.get("brakes"):
        text.append(f"Bremsen: {len(state['brakes'])}")
    if state.get("urteil"):
        text.append("URTEIL: " + state["urteil"]["text"][:300])
    text += ["", "Letzte Autopilot-Einträge:"] + [l[:95] for l in state.get("log", [])[-6:]]
    axes[1, 2].text(0, 1, "\n".join(text), va="top", ha="left", fontsize=8.3, color=INK2, transform=axes[1, 2].transAxes,
                    wrap=True)
    fig.suptitle("Phase 11 · Generalist (A mit Spiegel, B ohne)", x=0.01, ha="left", fontsize=13, fontweight="bold",
                 color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = A.STATE_DIR / "status.png"
    fig.savefig(out, dpi=100)
    plt.close(fig)
    print("\n".join(text))
    print("Bild:", out)


if __name__ == "__main__":
    main()
