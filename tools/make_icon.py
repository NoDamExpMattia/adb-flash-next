"""Turns assets/logo.png into assets/app.ico (all the sizes Windows uses).

Run from the project root:   python tools/make_icon.py
Use a square PNG of at least 256 x 256 pixels (512 or 1024 is better), ideally with a
transparent background. A non-square picture is centred on a transparent square.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "logo.png"
TARGET = ROOT / "assets" / "app.ico"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    if not SOURCE.is_file():
        print(f"Missing {SOURCE}. Put your logo there (PNG) or copy a ready-made .ico to {TARGET}.")
        return 1
    image = Image.open(SOURCE).convert("RGBA")
    side = max(image.size)
    if side < 256:
        print(f"Warning: the logo is only {image.width} x {image.height}; 256 x 256 or more looks sharper.")
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    canvas = canvas.resize((256, 256), Image.Resampling.LANCZOS)
    canvas.save(TARGET, format="ICO", sizes=SIZES)
    print(f"Created {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
