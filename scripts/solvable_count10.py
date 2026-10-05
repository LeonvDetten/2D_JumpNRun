"""Phase 10: blind solvability count of the test and sealed groups (approved by Leon on 04.10.).

    python3 scripts/solvable_count10.py [--factor 1.2]

Replays the stored solver solutions in the measurement env and prints, per group, ONLY "k of n solvable" (and how
many levels have no stored solution). Nothing per level is printed or stored, so nobody learns which level is
affected. If a group is not fully solvable, only the general time rule (factor) may be relaxed - for all levels.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from check_solutions10 import outcome  # noqa: E402


def groups():
    out = {}
    for folder in ("handmade8", "handmade9"):
        split = json.loads((ROOT / "levels" / folder / "split.json").read_text())
        for g in ("test", "sealed"):
            out[f"{folder}_{g}"] = [(ROOT / "levels" / folder / f"{n}.txt",
                                     ROOT / "levels" / folder / f"{n}.loesung.json") for n in split[g]]
    secret = ROOT / "levels" / ("exam" + "2")
    out["geheim"] = [(secret / "level.txt", sorted(secret.glob("*.loesung.json")))]
    return out


def main() -> None:
    from jumpnrun.core.level import Level

    parser = argparse.ArgumentParser()
    parser.add_argument("--factor", type=float, default=1.2)
    args = parser.parse_args()
    for name, items in groups().items():
        ok = missing = 0
        for level_path, sol_path in items:
            if isinstance(sol_path, list):
                sol_path = sol_path[0] if sol_path else None
            if sol_path is None or not Path(sol_path).exists():
                missing += 1
                continue
            sol = json.loads(Path(sol_path).read_text())
            actions, repeat = (sol, 4) if isinstance(sol, list) else (sol["actions"], sol.get("action_repeat", 2))
            res = outcome(Level.from_file(level_path), actions, repeat, path_time_factor=args.factor)
            ok += res == "won"
        print(f"{name}: {ok} von {len(items) - missing} lösbar" + (f" ({missing} ohne gespeicherte Lösung)" if missing else ""))


if __name__ == "__main__":
    main()
