"""Phase 10: every stored solver solution of the allowed level groups must win in the measurement env.

    python3 scripts/check_solutions10.py            # dev levels (exam, test series, handmade8/9 dev) + guards

The measurement env (modelinfo.env_kwargs: progress="path", time limit from the way length) must not cut off a
valid solution as "stuck" or "timeout" - in phase 9 it did for serpentine and spiegelweg. Only allowed groups
are checked here; test and sealed groups only get the blind count of scripts/solvable_count10.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def allowed_solutions():
    """[(name, level path, actions, action_repeat)] of the dev group and the phase-10 guard levels (val + test)."""

    out = []
    exam = ROOT / "levels/exam/level.txt"
    out.append(("pruefung", exam, json.loads((ROOT / "levels/exam/level.loesung.json").read_text()), 4))
    for p in sorted((ROOT / "levels/test_serie").glob("*.txt")):
        sol = json.loads(p.with_suffix(".loesung.json").read_text())
        out.append((f"serie_{p.stem}", p, sol["actions"], sol["action_repeat"]))
    for folder in ("handmade8", "handmade9"):
        split = json.loads((ROOT / "levels" / folder / "split.json").read_text())
        for n in split["dev"]:
            sol = json.loads((ROOT / "levels" / folder / f"{n}.loesung.json").read_text())
            out.append((f"{folder}_{n}", ROOT / "levels" / folder / f"{n}.txt", sol["actions"], sol["action_repeat"]))
    guard = ROOT / "levels/handmade10/split.json"
    if guard.exists():  # the phase-10 guard levels are built by Claude for monitoring: all of them are checked
        split = json.loads(guard.read_text())
        for n in split["val"] + split["test"] + split.get("val_plus", []):
            sol = json.loads((ROOT / "levels/handmade10" / f"{n}.loesung.json").read_text())
            out.append((f"handmade10_{n}", ROOT / "levels/handmade10" / f"{n}.txt", sol["actions"], sol["action_repeat"]))
    return out


def outcome(level, actions, repeat, **env_kw):
    from jumpnrun.rl.env import JumpNRunEnv, fixed_levels

    kw = dict(overview=True, obs_v3=True, progress="path")
    kw.update(env_kw)
    env = JumpNRunEnv(fixed_levels([level]), action_repeat=repeat, **kw)
    env.reset(seed=0)
    for a in actions:
        _, _, term, trunc, info = env.step(a)
        if term or trunc:
            return info["episode_end"]["outcome"]
    return "running"


def main() -> int:
    from jumpnrun.core.level import Level

    bad = []
    for name, path, actions, repeat in allowed_solutions():
        res = outcome(Level.from_file(path), actions, repeat)
        print(f"{name:28s} {res}")
        if res != "won":
            bad.append(name)
    print("NICHT GEWONNEN:", bad or "keine")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
