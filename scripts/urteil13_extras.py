"""Phase 13 verdict extras (T = 0.3, seeds 1 and 2): mirrored v13 jump probes (left), spiegelweg (16 x 2),
the three fork dev levels (12 x 2 each). -> runs/phase13/urteil_extras.json

    OMP_NUM_THREADS=1 python3 scripts/urteil13_extras.py tag=path ...
"""

import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def job(spec):
    import numpy as np
    import torch

    from jumpnrun.rl import milestones9 as m9
    from jumpnrun.rl.evaluate import evaluate_levels
    from jumpnrun.rl.milestones13 import extra_levels
    from jumpnrun.rl.modelinfo import PLAY_TEMPERATURE, load_model

    tag, path = spec.split("=", 1)
    torch.set_num_threads(1)
    model = load_model(ROOT / path)
    links, sw = extra_levels()
    dev = {n: lv for n, lv, _ in m9.dev_levels()}
    sets = {"links_spruenge": links, "spiegelweg": [sw] * 16}
    for n in ("hand_doppelgabel", "hand9_gabel_drei", "hand9_kreuzung"):
        dev[n].needs_path = True
        sets[n] = [dev[n]] * 12
    out = {}
    for name, levels in sets.items():
        won = of = 0
        for seed in (1, 2):
            np.random.seed(seed)
            torch.manual_seed(seed)
            r = evaluate_levels(model, levels, deterministic=False, temperature=PLAY_TEMPERATURE)
            won += sum(int(x["won"]) for x in r)
            of += len(r)
        out[name] = {"won": won, "of": of}
    return tag, out


def main():
    specs = [s for s in sys.argv[1:] if (ROOT / s.split("=", 1)[1]).exists()]
    res = {}
    with Pool(4) as pool:
        for tag, out in pool.imap_unordered(job, specs):
            res[tag] = out
            print(tag, json.dumps(out), flush=True)
    (ROOT / "runs/phase13/urteil_extras.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
