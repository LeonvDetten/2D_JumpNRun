"""Phase 10 dashboard: the two arms of the current round side by side.

    python3 -m jumpnrun.rl.status10              # -> runs/phase10/status.png + short text

Panels: alt value (dev_alt; EMA solid, raw dotted) against the start-model and P8 bases, F value (skills) and
dev_neu, drift KL to phase 8 with the brake threshold S_KL, probes (latest EMA), what training plays (shares of
training steps per source; round A: 100 % phase 8), text (exam, protection, brakes, autopilot log).
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter

import numpy as np

from jumpnrun.rl import autopilot10 as A

INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COLORS = ["#2a78d6", "#eb6834"]
S_KL = 0.0527


def arms(state: dict) -> dict:
    import os

    if os.environ.get("PHASE10_ARMS"):  # e.g. "lehrer=runs/phase10_d_lehrer,kontrolle_c=runs/phase10_c_kontrolle"
        return dict(kv.split("=") for kv in os.environ["PHASE10_ARMS"].split(","))
    if state["stage"] == "A":
        return A.arm_runs_a()
    from jumpnrun.rl import autopilot10_bc as B

    if state["stage"] in ("demos",):
        return A.arm_runs_a()
    if state["stage"] == "C" and state.get("c_runs"):
        return state["c_runs"]
    return B.b_runs()


def series(run: str, kind: str):
    ms = A.milestones(run)
    return sorted(((int(k.split(":")[0]), v) for k, v in ms.items() if k.split(":")[1] == kind), key=lambda x: x[0])


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
    runs = arms(state)
    start = A.START_STEPS
    if state["stage"] in ("C", "auswahl") or os.environ.get("PHASE10_START"):
        start = int(os.environ.get("PHASE10_START", state["rounds"].get("C", {}).get("start_steps", start)))
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
    for (name, run), color in zip(runs.items(), COLORS):
        ema, raw = series(run, "ema"), series(run, "raw")
        x = lambda s: (s - start) / 1e6  # noqa: E731
        if ema:
            axes[0, 0].plot([x(s) for s, _ in ema], [100 * r["dev_alt"] for _, r in ema], "o-", color=color,
                            linewidth=2, label=f"{name} (EMA)")
            axes[0, 1].plot([x(s) for s, _ in ema], [100 * r["F"] for _, r in ema], "o-", color=color, linewidth=2,
                            label=f"{name}: F")
            axes[0, 1].plot([x(s) for s, _ in ema], [100 * r["dev_neu"] for _, r in ema], "--", color=color,
                            linewidth=1.3, label=f"{name}: dev_neu")
            last = ema[-1][1]
            skills = sorted(last["proben_stoch"])
            y = np.arange(len(skills))
            off = 0.2 if color == COLORS[0] else -0.2
            axes[1, 0].barh(y + off, [100 * last["proben_stoch"][s]["won"] / last["proben_stoch"][s]["of"]
                                      for s in skills], height=0.38, color=color, label=name)
            axes[1, 0].set_yticks(y, skills)
            p = last["dev"]["pruefung"]
            lines.append(f"{name}: {x(ema[-1][0]):+.1f} Mio., alt {last['alt']:.1%}, F {last['F']:.1%}, "
                         f"Prüfung {p['won']}/{p['of']}" + (f", Schutz {last['schutz']['won']}/{last['schutz']['of']}"
                                                           if "schutz" in last else ""))
        if raw:
            axes[0, 0].plot([x(s) for s, _ in raw], [100 * r["dev_alt"] for _, r in raw], ":", color=color,
                            linewidth=1.2, label=f"{name} (roh)")
        drift = A.ROOT / run / "drift.json"
        if drift.exists():
            d = sorted(json.loads(drift.read_text()).values(), key=lambda v: v["steps"])
            axes[0, 2].plot([x(v["steps"]) for v in d], [v["kl"] for v in d], color=color, linewidth=2,
                            label=f"{name}: KL")
            lines.append(f"{name}: Drift-KL zuletzt {d[-1]['kl']:.4f}, P(links+springen) alt {d[-1]['p_a6']:.4f}"
                         if d else "")
        shares, n = step_shares(run)
        if n:
            keys = ["p8", "skill", "v10"]
            off = 0.2 if color == COLORS[0] else -0.2
            axes[1, 1].barh(np.arange(3) + off, [100 * shares.get(k, 0) / n for k in keys], height=0.38,
                            color=color, label=name)
            axes[1, 1].set_yticks(np.arange(3), ["Phase 8", "Übung", "lange v10"])
    for basis, label, style in ((A.start_basis(), "Startmodell", "-."), (A.p8_basis(), "P8", "--")):
        if basis is not None:
            axes[0, 0].axhline(100 * basis, color=INK2, linewidth=1, linestyle=style, label=label)
    if A.start_basis() is not None:
        axes[0, 0].axhline(100 * (A.start_basis() - 0.03), color="#b3261e", linewidth=0.8, linestyle=":",
                           label="Start − 3 Pp")
    axes[0, 2].axhline(S_KL, color="#b3261e", linewidth=1, linestyle=":", label="Bremsschwelle S_KL")
    for ax in (axes[0, 0], axes[0, 1], axes[0, 2]):
        ax.set_xlabel("Mio. Schritte seit Rundenstart")
        ax.legend(frameon=False, fontsize=8, loc="best")
    axes[0, 0].set_title("Alt-Wert: dev_alt (11 alte Dev-Level) in %", loc="left")
    axes[0, 1].set_title("Fähigkeitswert F und dev_neu in %", loc="left")
    axes[0, 2].set_title("Drift zu Phase 8 (KL auf alten Zuständen)", loc="left")
    axes[1, 0].set_title("Proben stochastisch (letzter EMA-Stand) in %", loc="left")
    axes[1, 0].legend(frameon=False, fontsize=8)
    axes[1, 1].set_title("Anteile der Trainingsschritte (letzte 4000 Episoden) in %", loc="left")
    axes[1, 1].legend(frameon=False, fontsize=8)
    axes[1, 2].axis("off")
    hours = (time.time() - state["started"]) / 3600
    text = [f"Phase 10 · Stufe {state['stage']} · {hours:.1f} h von 48 h"] + [l for l in lines if l]
    if state.get("brakes"):
        text.append(f"Bremsen: {len(state['brakes'])}")
    text += ["", "Letzte Autopilot-Einträge:"] + [l[:95] for l in state.get("log", [])[-6:]]
    axes[1, 2].text(0, 1, "\n".join(text), va="top", ha="left", fontsize=8.5, color=INK2, transform=axes[1, 2].transAxes)
    fig.suptitle(f"Phase 10 · Runde {state['stage']}", x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = A.STATE_DIR / "status.png"
    fig.savefig(out, dpi=100)
    plt.close(fig)
    print("\n".join(text))
    print("Bild:", out)


if __name__ == "__main__":
    main()
