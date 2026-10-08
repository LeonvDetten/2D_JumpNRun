"""Phase 12: teacher routing from the validation profile (runs/phase12/endvergleich.json, "familien" - fresh generator
levels from a seed space never trained on; test levels are never used).

    python3 scripts/lehrer_profil12.py        # -> runs/phase12/lehrer_routing.json

Rule (plan): per family the model with the highest win rate; unless it beats P8 by >= 5 Pp, P8 (the most conservative
teacher); no teacher where nobody reaches 30 %. Families of generator v11 never get a teacher.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from endvergleich12 import MODELS  # noqa: E402


def main():
    fam = json.loads((ROOT / "runs/phase12/endvergleich.json").read_text())["familien"]
    tags = list(fam)
    teachers, routing, why = [], {}, {}

    def index(tag):
        if MODELS[tag] not in teachers:
            teachers.append(MODELS[tag])
        return teachers.index(MODELS[tag])

    for name in fam["p8"]:
        rates = {t: fam[t][name]["won"] / fam[t][name]["of"] for t in tags}
        best = max(rates, key=lambda t: (rates[t], t == "p8"))
        if rates[best] < 0.30:
            routing[name], pick = -1, None
        elif best != "p8" and rates[best] < rates["p8"] + 0.05:
            pick = "p8"
        else:
            pick = best
        if pick:
            routing[name] = index(pick)
        why[name] = {"lehrer": pick, "quoten": {t: round(r, 3) for t, r in rates.items()}}
    routing["v9_leicht"] = index("p8")  # tiers 0-3 (everyone wins them): P8
    routing["_p8"] = index("p8")  # MixSource: P8 never teaches on levels with forks / channels
    for name in ("v11_spruenge", "v11_strukturen", "v11_gemischt", "v11_lang"):
        routing[name] = -1
    out = {"teachers": teachers, "routing": routing, "begruendung": why}
    (ROOT / "runs/phase12/lehrer_routing.json").write_text(json.dumps(out, indent=1))
    for name, w in why.items():
        print(f"{name:26s} -> {w['lehrer']}")
    print("Lehrer:", teachers)


if __name__ == "__main__":
    main()
