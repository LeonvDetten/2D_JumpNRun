"""Neustart dashboard: the fresh-network arm(s) against P8, the P8 lineage and Phase-10 round B.

    OMP_NUM_THREADS=1 nice -n 10 .venv/bin/python -m jumpnrun.rl.status_neustart   # -> runs/neustart/status.png

Panels: alt value (dev_alt; EMA solid, raw dotted, EMA2 squares) with the P8 basis, the P8 lineage and the abort
thresholds; F and dev_neu; guard val (full measurements) with the select10 gate; stochastic probes of the latest
EMA against P8; what training plays (shares of steps per source, curriculum tier, practice difficulty); text
(speed, projected end, kickstarting weight, drift, where the exam attempts end, autopilot log).
Where the exam attempts end: the latest EMA plays the exam 32 times (stochastic, own seeds 9100+), cached per
checkpoint in runs/<arm>/pruefung_enden.json.
"""

from __future__ import annotations

import json
import time
from collections import Counter

import numpy as np

from jumpnrun.rl import autopilot_neustart as A

INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COLORS = ["#2a78d6", "#eb6834"]
GREY = "#a3a29e"
P8_BASIS = 0.6643  # pooled dev_alt of 3 full P8 measurements (runs/phase10/baseline_p8.json)
P8_GUARD = 0.7734  # runs/phase10/guard_valid.json
LINEAGE = [(3.6, 4.0), (11.05, 24.4), (17.0, 35.2), (30.0, 39.8), (35.0, 52.6), (50.0, 66.4)]  # P8 lineage dev_alt
B_START = 50_000_000
SECTIONS = ((0, 36, "Start/Gegnerregen"), (36, 98, "Gabelung oben"), (98, 160, "Trittsteine"),
            (160, 250, "Diagonalen"), (250, 10**6, "Ziel"))


def series(ms: dict, kind: str):
    return sorted(((int(k.split(":")[0]), v) for k, v in ms.items() if k.split(":")[1] == kind), key=lambda x: x[0])


def step_shares(run: str, last: int = 4000):
    path = A.ROOT / run / "episodes.jsonl"
    if not path.exists():
        return Counter(), 0
    c = Counter()
    with open(path, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 600 * last))
        lines = f.read().decode("utf-8", "ignore").splitlines()[1:]
    for line in lines[-last:]:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        c[e.get("mix") or "p8"] += e["steps"]
    return c, sum(c.values())


def exam_ends(run: str, ckpt, attempts: int = 32) -> dict:
    """Where the attempts of `ckpt` end on the exam (cached per checkpoint)."""

    import torch

    from jumpnrun.core.constants import TILE
    from jumpnrun.core.level import Level
    from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
    from jumpnrun.rl.modelinfo import env_kwargs, load_model

    path = A.ROOT / run / "pruefung_enden.json"
    cache = json.loads(path.read_text()) if path.exists() else {}
    if ckpt.name in cache:
        return cache[ckpt.name]
    torch.set_num_threads(1)
    torch.manual_seed(9100)
    model = load_model(ckpt)
    level = Level.from_file(A.ROOT / "levels/exam/level.txt")
    envs = [JumpNRunEnv(fixed_levels([level]), **env_kwargs(model)) for _ in range(attempts)]
    obs = [e.reset(seed=9100 + i)[0] for i, e in enumerate(envs)]
    ends = [None] * attempts
    active = list(range(attempts))
    while active:
        batch = {k: np.stack([obs[i][k] for i in active]) for k in obs[active[0]]}
        actions, _ = model.predict(batch, deterministic=False)
        still = []
        for i, a in zip(active, actions):
            obs[i], _, term, trunc, info = envs[i].step(int(a))
            if term or trunc:
                e = info["episode_end"]
                ends[i] = {"won": e["won"], "outcome": e["outcome"], "col": envs[i].sim.player.x // TILE}
            else:
                still.append(i)
        active = still
    out = {"won": sum(e["won"] for e in ends), "of": attempts, "sections": {}}
    for e in ends:
        if e["won"]:
            continue
        name = next(n for lo, hi, n in SECTIONS if lo <= e["col"] < hi)
        sec = out["sections"].setdefault(name, {"n": 0, "outcomes": {}})
        sec["n"] += 1
        sec["outcomes"][e["outcome"]] = sec["outcomes"].get(e["outcome"], 0) + 1
    cache[ckpt.name] = out
    path.write_text(json.dumps(cache, indent=1))
    return out


def kick_weight(plan, steps: int) -> float:
    plan = sorted(plan)
    if steps <= plan[0][0]:
        return plan[0][1]
    for (s0, c0), (s1, c1) in zip(plan, plan[1:]):
        if steps < s1:
            return c0 + (c1 - c0) * (steps - s0) / (s1 - s0)
    return plan[-1][1]


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    state = A.load_state()
    pr = A.prereg()
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.titlesize": 11, "axes.titleweight": "bold",
                         "axes.titlecolor": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    fig, axes = plt.subplots(2, 3, figsize=(17, 8.8))
    for ax in axes.flat:
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    x = lambda s: s / 1e6  # noqa: E731
    # references: phase-10 round B (x = steps since its start) and the P8 lineage
    for name in ("b_kontrolle", "b_neu"):
        path = A.ROOT / f"runs/phase10_{name}/milestones10.json"
        if not path.exists():
            continue
        ms = json.loads(path.read_text())
        ema = series(ms, "ema")
        label = f"Phase 10 Runde B {name[2:]}"
        axes[0, 0].plot([x(s - B_START) for s, _ in ema], [100 * r["dev_alt"] for _, r in ema], color=GREY,
                        linewidth=1, linestyle="-" if name == "b_kontrolle" else "--", label=label)
        axes[0, 1].plot([x(s - B_START) for s, _ in ema], [100 * r["F"] for _, r in ema], color=GREY, linewidth=1,
                        linestyle="-" if name == "b_kontrolle" else "--", label=label + ": F")
        full = [(s, r) for s, r in ema if "waechter_val_rate" in r]
        axes[0, 2].plot([x(s - B_START) for s, _ in full], [100 * r["waechter_val_rate"] for _, r in full],
                        color=GREY, linewidth=1, linestyle="-" if name == "b_kontrolle" else "--", label=label)
    axes[0, 0].plot([m for m, _ in LINEAGE], [v for _, v in LINEAGE], "x", color=INK2, markersize=7,
                    label="P8-Linie (PPO ab frisch, klein)")
    axes[0, 0].axhline(100 * P8_BASIS, color=INK2, linewidth=1, linestyle="--", label="P8-Basis 66,4 %")
    axes[0, 0].axhline(100 * (P8_BASIS - 0.03), color="#2e7d32", linewidth=0.8, linestyle=":", label="Alt-Tor dev_alt")
    axes[0, 2].axhline(100 * P8_GUARD, color=INK2, linewidth=1, linestyle="--", label="P8 77,3 %")
    axes[0, 2].axhline(100 * (P8_GUARD - 0.05), color="#2e7d32", linewidth=0.8, linestyle=":", label="Alt-Tor Wächter")
    for rule in pr["abbruchregel"]:
        m = max(rule["millionen"])
        for key, lim in rule["abbruch_wenn_unter"].items():
            ax = {"dev_alt": axes[0, 0], "F": axes[0, 1], "waechter_val": axes[0, 2]}[key]
            ax.plot([m], [100 * lim], "v", color="#b3261e", markersize=8)
    axes[0, 0].plot([], [], "v", color="#b3261e", label="Abbruchschwelle")
    lines = []
    for (arm, info), color in zip(sorted(state.get("arms", {}).items()), COLORS):
        run = A.run_dir(arm)
        ms = A.milestones(arm)
        ema, ema2, raw = series(ms, "ema"), series(ms, "ema2"), series(ms, "raw")
        if ema:
            axes[0, 0].plot([x(s) for s, _ in ema], [100 * r["dev_alt"] for _, r in ema], "o-", color=color,
                            linewidth=2, label=f"{arm} EMA")
            axes[0, 1].plot([x(s) for s, _ in ema], [100 * r["F"] for _, r in ema], "o-", color=color, linewidth=2,
                            label=f"{arm}: F")
            axes[0, 1].plot([x(s) for s, _ in ema], [100 * r["dev_neu"] for _, r in ema], "--", color=color,
                            linewidth=1.3, label=f"{arm}: dev_neu")
            last = ema[-1][1]
            p = last["dev"]["pruefung"]
            lines.append(f"{arm}: EMA {x(ema[-1][0]):.0f} Mio.: dev_alt {last['dev_alt']:.1%}, F {last['F']:.1%}, "
                         f"dev_neu {last['dev_neu']:.1%}, Prüfung {p['won']}/{p['of']}")
            skills = sorted(last["proben_stoch"])
            base = json.loads((A.ROOT / "runs/phase10/baseline_p8.json").read_text())["p8:0"]["proben_stoch"]
            y = np.arange(len(skills))
            axes[1, 0].barh(y + 0.2, [100 * last["proben_stoch"][s]["won"] / last["proben_stoch"][s]["of"]
                                      for s in skills], height=0.38, color=color, label=f"{arm} EMA {x(ema[-1][0]):.0f} Mio.")
            axes[1, 0].barh(y - 0.2, [100 * base[s]["won"] / base[s]["of"] if s in base else 0 for s in skills],
                            height=0.38, color=GREY, label="P8")
            axes[1, 0].set_yticks(y, skills)
            ck = A.ROOT / run / "checkpoints" / f"ema_step_{ema[-1][0]:010d}.zip"
            if ck.exists():
                try:
                    ends = exam_ends(run, ck)
                    worst = sorted(ends["sections"].items(), key=lambda kv: -kv[1]["n"])[:3]
                    lines.append(f"{arm}: Prüfung stoch. {ends['won']}/{ends['of']}; Enden: " + ", ".join(
                        f"{n} {v['n']} ({', '.join(f'{k} {c}' for k, c in v['outcomes'].items())})" for n, v in worst))
                except Exception as exc:  # the dashboard must not fail on it
                    lines.append(f"{arm}: Prüfungs-Enden nicht messbar ({exc})")
        full = [(s, r) for s, r in sorted(ema + ema2, key=lambda t: t[0]) if "waechter_val_rate" in r]
        if full:
            axes[0, 2].plot([x(s) for s, _ in full], [100 * r["waechter_val_rate"] for _, r in full], "o",
                            color=color, label=f"{arm} EMA/EMA2")
        if ema2:
            axes[0, 0].plot([x(s) for s, _ in ema2], [100 * r["dev_alt"] for _, r in ema2], "s", color=color,
                            markersize=5, fillstyle="none", label=f"{arm} EMA2")
        if raw:
            axes[0, 0].plot([x(s) for s, _ in raw], [100 * r["dev_alt"] for _, r in raw], ":", color=color,
                            linewidth=1.2, label=f"{arm} roh")
        steps = A.last_step(arm)
        secs = A.ROOT / run / "seconds_used"
        if steps and secs.exists():
            used = float(secs.read_text() or 1)
            fps = steps / max(1.0, used)
            rest = (pr["ziel_schritte"] - steps) / max(1.0, fps) / 3600
            wall = (time.time() - state["ppo_started"]) / 3600 if state.get("ppo_started") else 0.0
            lines.append(f"{arm}: {steps / 1e6:.2f} Mio. Schritte, {fps:.0f}/s im Mittel, noch ~{rest:.1f} h bis "
                         f"{pr['ziel_schritte'] / 1e6:.0f} Mio. (Wanduhr {wall:.1f} von {pr['zeit_stunden']} h); "
                         f"Kickstart-Gewicht {kick_weight(pr['kickstart_plan'], steps):.2f}"
                         if pr["arme"][arm].get("kickstart") else "")
        cur = A.ROOT / run / "curriculum.json"
        if cur.exists():
            c = json.loads(cur.read_text())
            skill = c.get("skill", {}).get("level", {})
            lines.append(f"{arm}: Curriculum Stufe {c['unlocked']} (v10 ab 10), Übung d: "
                         + " ".join(f"{k[:6]}{v}" for k, v in skill.items()))
        drift = A.ROOT / run / "drift.json"
        if drift.exists():
            d = sorted(json.loads(drift.read_text()).values(), key=lambda v: v["steps"])
            if d:
                lines.append(f"{arm}: Drift-KL zu P8 {d[-1]['kl']:.3f}, P(links+springen) auf alten Zuständen "
                             f"{d[-1]['p_a6']:.4f}")
        for name, nums in info.get("regel", {}).items():
            lines.append(f"{arm}: Regel {name}: dev_alt {nums['dev_alt']:.1%}, F {nums['F']:.1%}"
                         + (f", Wächter {nums['waechter_val']:.1%}" if "waechter_val" in nums else "")
                         + (" -> ABBRUCH" if nums["unter"] else " bestanden"))
        shares, n = step_shares(run)
        if n:
            keys = ["p8", "skill", "v10"]
            axes[1, 1].barh(np.arange(3), [100 * shares.get(k, 0) / n for k in keys], height=0.5, color=color,
                            label=arm)
            axes[1, 1].set_yticks(np.arange(3), ["Phase 8", "Übung", "lange v10"])
            for i, k in enumerate(keys):
                axes[1, 1].text(100 * shares.get(k, 0) / n + 1, i, f"{100 * shares.get(k, 0) / n:.0f} % "
                                f"(Soll {100 * pr['mischung'][k]:.0f})", va="center", fontsize=8, color=INK2)
    for ax in (axes[0, 0], axes[0, 1], axes[0, 2]):
        ax.set_xlabel("Mio. Schritte seit Phasenstart")
        ax.legend(frameon=False, fontsize=7.5, loc="best")
    axes[0, 0].set_title("Alt: dev_alt (11 alte Dev-Level) in %", loc="left")
    axes[0, 1].set_title("Fähigkeitswert F und dev_neu in %", loc="left")
    axes[0, 2].set_title("Wächter-Val (lange Level, volle Messungen) in %", loc="left")
    axes[1, 0].set_title("Proben stochastisch (letzter EMA-Stand) in %", loc="left")
    axes[1, 0].legend(frameon=False, fontsize=8)
    axes[1, 1].set_title("Anteile der Trainingsschritte (letzte 4000 Episoden) in %", loc="left")
    axes[1, 1].set_xlim(0, 110)
    axes[1, 2].axis("off")
    hours = (time.time() - state["started"]) / 3600
    text = [f"Neustart · Stufe {state['stage']} · {hours:.1f} h seit Beginn"] + [l for l in lines if l]
    text += ["", "Letzte Autopilot-Einträge:"] + [l[:100] for l in state.get("log", [])[-6:]]
    axes[1, 2].text(0, 1, "\n".join(text), va="top", ha="left", fontsize=8, color=INK2, transform=axes[1, 2].transAxes,
                    wrap=True)
    fig.suptitle("Neustart-Arm (frisches Netz, BC + Kickstarting)", x=0.01, ha="left", fontsize=13,
                 fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = A.STATE_DIR / "status.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100)
    plt.close(fig)
    print("\n".join(text))
    print("Bild:", out)


if __name__ == "__main__":
    main()
