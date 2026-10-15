"""Shared helpers for the mobile export tools: they import the desktop package read-only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

MOBILE = Path(__file__).resolve().parents[1]
ROOT = MOBILE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PUBLIC = MOBILE / "public"
FIXTURES = MOBILE / "tests" / "fixtures"


def write_json(path: Path, data, compact: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False) if compact else json.dumps(data, indent=1, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.0f} KB)")
