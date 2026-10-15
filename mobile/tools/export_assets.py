"""Shrink the game's sprites for the phone: one sprite atlas at 2x the in-game size, the background, app icons.

    .venv/bin/python mobile/tools/export_assets.py
writes mobile/public/assets/{atlas.png,atlas.json,bg.jpg} and mobile/public/icons/*.png
"""

from __future__ import annotations

import json
import math

from PIL import Image, ImageDraw, ImageFilter

from _common import PUBLIC, ROOT

IMG = ROOT / "img"
SCALE = 2  # atlas pixels per logical pixel (the phone shows ~1.5 device pixels per logical pixel)
STATES = ("IDLE", "RUN", "JUMP", "ATTACK")
PLAYER_CROP = (200, 250, 200 + 825, 250 + 850)  # same crop as jumpnrun/render/assets.py


def sprites() -> dict:
    out = {}
    for state in STATES:
        for i in range(7):
            im = Image.open(IMG / "player_img" / f"2_entity_000_{state}_00{i}.png").convert("RGBA").crop(PLAYER_CROP)
            out[f"player_{state}_{i}"] = im.resize((40 * SCALE, 60 * SCALE), Image.LANCZOS)
    for i in range(10):
        im = Image.open(IMG / "chest_img" / f"chest1_{i}.png").convert("RGBA")
        out[f"chest_{i}"] = im.resize((60 * SCALE, 40 * SCALE), Image.NEAREST)  # pixel art: keep it crisp
    for side, d in (("r", 1), ("l", -1)):
        for i in range(3):
            im = Image.open(IMG / "enemy_img" / f"e1_{side}{i}.png").convert("RGBA")
            out[f"enemy_{d}_{i}"] = im.resize((40 * SCALE, 40 * SCALE), Image.NEAREST)
    out["block"] = Image.open(IMG / "ground_img" / "spaceground.png").convert("RGBA").resize((60 * SCALE, 60 * SCALE), Image.LANCZOS)
    out["bullet"] = Image.open(IMG / "bullet_img" / "bullet.png").convert("RGBA").resize((10 * SCALE, 5 * SCALE), Image.LANCZOS)
    return out


def pack(images: dict, width: int = 1024, pad: int = 2):
    """Shelf packing: tallest first, rows left to right."""

    order = sorted(images, key=lambda k: (-images[k].height, k))
    x = y = shelf = 0
    rects = {}
    for k in order:
        w, h = images[k].size
        if x + w + pad > width:
            x, y, shelf = 0, y + shelf + pad, 0
        rects[k] = (x, y, w, h)
        x += w + pad
        shelf = max(shelf, h)
    height = 1 << math.ceil(math.log2(y + shelf + pad))
    atlas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for k, (x, y, w, h) in rects.items():
        atlas.paste(images[k], (x, y))
    return atlas, rects


def icon(size: int, maskable: bool = False) -> Image.Image:
    """Space gradient with the pirate (idle frame) and a few stars."""

    im = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(im)
    for yy in range(size):
        k = yy / (size - 1)
        d.line([(0, yy), (size, yy)], fill=(int(28 - 20 * k), int(30 - 22 * k), int(80 - 60 * k), 255))
    for sx, sy, r in ((0.18, 0.2, 0.012), (0.8, 0.14, 0.016), (0.72, 0.36, 0.01), (0.12, 0.62, 0.01), (0.9, 0.7, 0.012)):
        d.ellipse([sx * size - r * size, sy * size - r * size, sx * size + r * size, sy * size + r * size],
                  fill=(220, 230, 255, 255))
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([size * 0.2, size * 0.25, size * 0.8, size * 0.95], fill=(255, 170, 60, 110))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(size * 0.08)))
    hero = Image.open(IMG / "player_img" / "2_entity_000_IDLE_000.png").convert("RGBA").crop(PLAYER_CROP)
    h = int(size * (0.62 if maskable else 0.74))
    hero = hero.resize((int(h * 825 / 850), h), Image.LANCZOS)
    im.alpha_composite(hero, ((size - hero.width) // 2, size - hero.height - int(size * (0.14 if maskable else 0.07))))
    return im.convert("RGB")


def main() -> None:
    images = sprites()
    atlas, rects = pack(images)
    out = PUBLIC / "assets"
    out.mkdir(parents=True, exist_ok=True)
    atlas.save(out / "atlas.png", optimize=True)
    (out / "atlas.json").write_text(json.dumps({"scale": SCALE, "frames": rects}, separators=(",", ":")) + "\n")
    bg = Image.open(IMG / "background_img" / "bg.jpg").convert("RGB").resize((2600, 1200), Image.LANCZOS)
    bg.save(out / "bg.jpg", quality=82, optimize=True, progressive=True)
    icons = PUBLIC / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    icon(180).save(icons / "apple-touch-icon.png", optimize=True)
    icon(192).save(icons / "icon-192.png", optimize=True)
    icon(512).save(icons / "icon-512.png", optimize=True)
    icon(512, maskable=True).save(icons / "icon-maskable-512.png", optimize=True)
    for p in sorted(list(out.iterdir()) + list(icons.iterdir())):
        print(f"{p.relative_to(ROOT)}  {p.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
