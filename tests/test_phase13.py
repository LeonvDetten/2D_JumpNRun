"""Phase 13: left levels, mirrored demos, adaptive curriculum."""

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_left_source_levels_go_left_and_are_reachable():
    from jumpnrun.levelgen.links import LeftSource, _reachable

    src = LeftSource()
    rng = random.Random(3)
    fams = set()
    for _ in range(25):
        level, tier = src(rng)
        fams.add(level.family)
        assert tier == LeftSource.LEFT_TIER and level.source == "links"
        assert level.chests[0][0] < level.spawn[0]  # chest on the left
        assert _reachable(level)
    assert {"links_spruenge", "links_trittsteine"} <= fams


def test_left_curriculum_moves():
    from jumpnrun.levelgen.links import LeftSource

    src = LeftSource()
    assert src.frontier() == 9

    class L:
        pass

    for t, won in ((10, True), (11, False)):
        for _ in range(12):
            lv = L()
            lv.links_tier = t
            src.feedback(lv, -9, won)
    assert src.frontier() == 10


def test_mirrored_demos_win():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import demos13

    pool = ROOT / "runs/demos12/demos.jsonl"
    if not pool.exists():
        return
    src = [json.loads(l) for l in pool.read_text().splitlines()[:5]]
    assert all(demos13.mirrored(d) for d in src)


def test_left_levels_are_not_measurement_levels():
    from jumpnrun.levelgen.links import LeftSource
    from jumpnrun.rl import milestones9 as m9

    dev = {lv.to_text() for _, lv, _ in m9.dev_levels()}
    rng = random.Random(5)
    src = LeftSource()
    for _ in range(15):
        level, _ = src(rng)
        assert level.to_text() not in dev
