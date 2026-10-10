"""Phase 12 diagnosis: what goes wrong where? Per scorecard category, for one model:

- wins sampled (the scorecard rule) AND deterministic (always the most likely action) - the gap is the cost of
  "unsure" play,
- progress along the way, the causes of the lost attempts (pit, enemy, stuck, time),
- decision certainty: mean probability of the chosen-most-likely action and the share of unsure decisions
  (top action below 50 %).

    OMP_NUM_THREADS=1 python3 -m jumpnrun.rl.diagnose12 eval models/phase12_kandidat.zip --tag p12 --seed 1
    python3 -m jumpnrun.rl.diagnose12 bild --tags p12 neustart phase11 p8 --out docs/.../diagnose.png

Results: runs/phase12/diagnose_<tag>.json. The exam is a single level: deterministic it is one fixed run.
"""

from __future__ import annotations

import argparse
import collections
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from jumpnrun.rl import scorecard12 as S

ROOT = S.ROOT
OUT = ROOT / "runs/phase12"
CAUSES = (("died_pit", "Abgrund"), ("died_enemy", "Gegner"), ("stuck", "hängen geblieben"), ("timeout", "Zeit um"))
UNSURE = 0.5


def rollout(model, levels, deterministic: bool):
    """Like evaluate.evaluate_levels, but also records the policy's action probabilities."""

    import torch

    from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
    from jumpnrun.rl.modelinfo import env_kwargs

    envs = [JumpNRunEnv(fixed_levels([lv]), **env_kwargs(model)) for lv in levels]
    obs = [env.reset(seed=i)[0] for i, env in enumerate(envs)]
    results = [None] * len(envs)
    stats = [[0, 0.0, 0, 0.0] for _ in envs]  # steps, sum top prob, unsure steps, sum entropy
    active = list(range(len(envs)))
    while active:
        batch = {key: np.stack([obs[i][key] for i in active]) for key in obs[active[0]]}
        with torch.no_grad():
            t, _ = model.policy.obs_to_tensor(batch)
            probs = model.policy.get_distribution(t).distribution.probs
            acts = probs.argmax(1) if deterministic else torch.multinomial(probs, 1).squeeze(1)
            top = probs.max(1).values
            ent = -(probs * probs.clamp_min(1e-9).log()).sum(1)
        still = []
        for k, i in enumerate(active):
            s = stats[i]
            s[0] += 1
            s[1] += float(top[k])
            s[2] += int(top[k] < UNSURE)
            s[3] += float(ent[k])
            obs[i], _, term, trunc, info = envs[i].step(int(acts[k]))
            if term or trunc:
                results[i] = dict(info["episode_end"], steps_taken=s[0], top=s[1] / s[0], unsure=s[2] / s[0],
                                  entropy=s[3] / s[0])
            else:
                still.append(i)
        active = still
    return results


def _job(args):
    import torch

    from jumpnrun.rl.modelinfo import load_model

    path, name, seed, det = args
    torch.set_num_threads(1)
    cat, levels, n = S.components()[name]
    model = load_model(path)
    np.random.seed(seed)
    torch.manual_seed(seed)
    res = rollout(model, levels * n, det) if levels else []
    causes = collections.Counter(r.get("outcome", "?") for r in res if not r["won"])
    return name, det, {"kat": cat, "won": sum(int(r["won"]) for r in res), "of": len(res),
                       "fortschritt": float(np.mean([r["progress"] for r in res])) if res else 0.0,
                       "ursachen": dict(causes),
                       "sicherheit": float(np.mean([r["top"] for r in res])) if res else 0.0,
                       "unsicher": float(np.mean([r["unsure"] for r in res])) if res else 0.0,
                       "entropie": float(np.mean([r["entropy"] for r in res])) if res else 0.0}


def evaluate(path, seed: int = 1, procs: int = 4) -> dict:
    jobs = [(str(path), n, seed, det) for n in S.components() for det in (False, True)]
    out = {"zufaellig": {}, "deterministisch": {}}
    with Pool(procs) as pool:
        for name, det, r in pool.imap_unordered(_job, jobs):
            out["deterministisch" if det else "zufaellig"][name] = r
    out["kategorien"] = {}
    for mode in ("zufaellig", "deterministisch"):
        comp = out[mode]
        cats = []
        for k in range(len(S.CATS)):
            cs = [c for c in comp.values() if c["kat"] == k and c["of"]]
            causes = collections.Counter()
            for c in cs:
                causes.update(c["ursachen"])
            lost = sum(causes.values())
            cats.append({"rate": float(np.mean([c["won"] / c["of"] for c in cs])),
                         "fortschritt": float(np.mean([c["fortschritt"] for c in cs])),
                         "sicherheit": float(np.mean([c["sicherheit"] for c in cs])),
                         "unsicher": float(np.mean([c["unsicher"] for c in cs])),
                         "ursachen": {k2: causes.get(k2, 0) / lost if lost else 0.0 for k2, _ in CAUSES}})
        out["kategorien"][mode] = cats
        out[f"generalist_{mode}"] = float(np.mean([c["rate"] for c in cats]))
    return out


# --------------------------------------------------------------------------------------------- picture
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def picture(tags, names, out: Path, title: str) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = {t: json.loads((OUT / f"diagnose_{t}.json").read_text()) for t in tags}
    main = data[tags[0]]
    labels = [c.split(" ", 1)[1] for c in S.CATS]
    x = np.arange(len(labels))
    fig = plt.figure(figsize=(16, 13), facecolor=SURFACE)
    gs = fig.add_gridspec(3, 2, height_ratios=[1.1, 1, 1], hspace=0.55, wspace=0.18)

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

    # A: sampled vs deterministic wins per category
    ax = fig.add_subplot(gs[0, :])
    style(ax, "gewonnen in %")
    z = [100 * c["rate"] for c in main["kategorien"]["zufaellig"]]
    d = [100 * c["rate"] for c in main["kategorien"]["deterministisch"]]
    w = 0.38
    ax.bar(x - w / 2 - 0.01, z, w, color=BLUE, label="zufällig gezogen (Scorecard-Regel)")
    ax.bar(x + w / 2 + 0.01, d, w, color=ORANGE, label="deterministisch (immer die wahrscheinlichste Aktion)")
    for i in range(len(x)):
        ax.text(x[i] - w / 2, z[i] + 1.5, f"{z[i]:.0f}", ha="center", fontsize=9, color=INK)
        ax.text(x[i] + w / 2, d[i] + 1.5, f"{d[i]:.0f}", ha="center", fontsize=9, color=INK)
    ax.set_xticks(x, labels, fontsize=10, color=INK)
    ax.set_ylim(0, 112)
    ax.legend(loc="upper left", frameon=False, fontsize=10, ncol=2)
    ax.set_title(f"{names[0]}: Generalist zufällig {100 * main['generalist_zufaellig']:.1f} %  ·  "
                 f"deterministisch {100 * main['generalist_deterministisch']:.1f} %  (Prüfung deterministisch = ein "
                 f"einziger fester Ablauf)", loc="left", fontsize=12, color=INK)

    # B: causes of the lost attempts (sampled)
    ax = fig.add_subplot(gs[1, 0])
    style(ax, "Anteil der verlorenen Versuche in %")
    bottom = np.zeros(len(x))
    for (key, label), color in zip(CAUSES, (BLUE, ORANGE, AQUA, YELLOW)):
        vals = np.array([100 * c["ursachen"][key] for c in main["kategorien"]["zufaellig"]])
        ax.bar(x, vals, 0.7, bottom=bottom, color=color, label=label, edgecolor=SURFACE, linewidth=2)
        for i, v in enumerate(vals):
            if v >= 12:
                ax.text(x[i], bottom[i] + v / 2, f"{v:.0f}", ha="center", va="center", fontsize=8, color="white")
        bottom += vals
    ax.set_xticks(x, labels, rotation=30, ha="right", fontsize=9, color=INK)
    ax.set_ylim(0, 100)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=4, frameon=False, fontsize=9)
    ax.set_title("Woran scheitern die Versuche? (zufällig gezogen)", loc="left", fontsize=11, color=INK, pad=28)

    # C: progress on lost + won attempts, sampled vs deterministic
    ax = fig.add_subplot(gs[1, 1])
    style(ax, "Fortschritt im Level in %")
    pz = [100 * c["fortschritt"] for c in main["kategorien"]["zufaellig"]]
    pd = [100 * c["fortschritt"] for c in main["kategorien"]["deterministisch"]]
    ax.bar(x - w / 2 - 0.01, pz, w, color=BLUE, label="zufällig")
    ax.bar(x + w / 2 + 0.01, pd, w, color=ORANGE, label="deterministisch")
    ax.set_xticks(x, labels, rotation=30, ha="right", fontsize=9, color=INK)
    ax.set_ylim(0, 105)
    ax.legend(loc="upper left", frameon=False, fontsize=9, ncol=2)
    ax.set_title("Wie weit kommt der Bot im Mittel?", loc="left", fontsize=11, color=INK)

    # D: decision certainty per category (sampled), all models
    ax = fig.add_subplot(gs[2, 0])
    style(ax, "unsichere Entscheidungen in %")
    colors = (BLUE, ORANGE, AQUA, YELLOW)
    ww = 0.8 / len(tags)
    for j, t in enumerate(tags):
        vals = [100 * c["unsicher"] for c in data[t]["kategorien"]["zufaellig"]]
        ax.bar(x - 0.4 + ww * (j + 0.5), vals, ww * 0.92, color=colors[j % 4], label=names[j])
    ax.set_xticks(x, labels, rotation=30, ha="right", fontsize=9, color=INK)
    ax.legend(loc="upper left", frameon=False, fontsize=9, ncol=len(tags))
    ax.set_title(f"Anteil der Schritte, in denen die beste Aktion < {int(100 * UNSURE)} % Wahrscheinlichkeit hat",
                 loc="left", fontsize=11, color=INK)

    # E: generalist sampled vs deterministic for all models
    ax = fig.add_subplot(gs[2, 1])
    style(ax, "Generalist-Wert in %")
    xm = np.arange(len(tags))
    gz = [100 * data[t]["generalist_zufaellig"] for t in tags]
    gd = [100 * data[t]["generalist_deterministisch"] for t in tags]
    ax.bar(xm - w / 2 - 0.01, gz, w, color=BLUE, label="zufällig")
    ax.bar(xm + w / 2 + 0.01, gd, w, color=ORANGE, label="deterministisch")
    for i in range(len(xm)):
        ax.text(xm[i] - w / 2, gz[i] + 1.5, f"{gz[i]:.1f}", ha="center", fontsize=9, color=INK)
        ax.text(xm[i] + w / 2, gd[i] + 1.5, f"{gd[i]:.1f}", ha="center", fontsize=9, color=INK)
    ax.set_xticks(xm, names, fontsize=10, color=INK)
    ax.set_ylim(0, 100)
    ax.legend(loc="upper right", frameon=False, fontsize=9, ncol=2)
    ax.set_title("Generalist-Wert je Modell (gleicher Seed)", loc="left", fontsize=11, color=INK)

    fig.suptitle(title, x=0.06, ha="left", fontsize=16, color=INK, fontweight="bold")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval")
    e.add_argument("model")
    e.add_argument("--tag", required=True)
    e.add_argument("--seed", type=int, default=1)
    e.add_argument("--procs", type=int, default=4)
    b = sub.add_parser("bild")
    b.add_argument("--tags", nargs="+", required=True)
    b.add_argument("--names", nargs="+")
    b.add_argument("--out", required=True)
    b.add_argument("--title", default="Phase 12 · Diagnose")
    args = parser.parse_args()
    if args.cmd == "eval":
        res = evaluate(ROOT / args.model, args.seed, args.procs)
        res["modell"] = args.model
        (OUT / f"diagnose_{args.tag}.json").write_text(json.dumps(res, indent=1))
        print(args.tag, f"zufällig {res['generalist_zufaellig']:.1%}, deterministisch "
                        f"{res['generalist_deterministisch']:.1%}")
    else:
        print(picture(args.tags, args.names or args.tags, Path(args.out), args.title))


if __name__ == "__main__":
    main()
