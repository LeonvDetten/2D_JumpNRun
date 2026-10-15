"""Bundle the desktop levels for the mobile app: tabs, titles, texts, proven bot ways and par times.

    .venv/bin/python mobile/tools/export_levels.py
writes mobile/public/data/levels.json and copies the jump catalogue to mobile/src/levelgen/.
"""

from __future__ import annotations

import shutil

from _common import MOBILE, PUBLIC, write_json

from jumpnrun.app import levels_index
from jumpnrun.editor.model import load_solution
from jumpnrun.levelgen.jump_catalog import CATALOG_PATH


def main() -> None:
    tabs = levels_index.scan()
    out = {"tabs": [], "tier_names": list(levels_index.TIER_NAMES)}
    for tab, folders in levels_index.CATEGORIES:
        entries = []
        for entry in tabs.get(tab, []):
            solution = load_solution(entry.path) if entry.path else None
            entries.append({
                "title": entry.title,
                "folder": entry.folder,
                "stem": entry.path.stem if entry.path else "",
                "text": entry.text,
                "key": entry.key,
                "par": entry.par_frames,
                "proven": entry.par_proven,
                # proven bot way in 2-frame steps (BOT_ACTIONS_V3 indices) - replayed by the menu demo
                "solution": solution or None,
            })
        out["tabs"].append({"name": tab, "folders": folders, "levels": entries})
    write_json(PUBLIC / "data" / "levels.json", out)
    shutil.copyfile(CATALOG_PATH, MOBILE / "src" / "levelgen" / "jump_catalog.json")
    print("copied jump_catalog.json")


if __name__ == "__main__":
    main()
