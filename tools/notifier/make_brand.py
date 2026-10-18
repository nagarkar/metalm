"""Makes the SuperLM favicon and logos in brand/ from the notifier icon.

The icon is drawn once, by make_icon.swift; this only crops, scales and lays it out,
so the favicon, the logos and the notification banner stay one picture.

    swift tools/notifier/make_icon.swift /tmp/icon.png
    python3 tools/notifier/make_brand.py /tmp/icon.png brand/

Needs Pillow and the macOS system font (SF Pro) for the wordmark.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# The rounded tile sits at 100..924 of 1024 in the icon (make_icon.swift).
TILE = (100 / 1024, 924 / 1024)
FONT = "/System/Library/Fonts/SFNS.ttf"
INK = {"light": (24, 20, 38, 255), "dark": (255, 255, 255, 255)}


def tile(icon: Image.Image, size: int) -> Image.Image:
    lo, hi = (round(f * icon.width) for f in TILE)
    return icon.crop((lo, lo, hi, hi)).resize((size, size), Image.LANCZOS)


def wordmark(icon: Image.Image, ink: tuple, height: int = 256) -> Image.Image:
    font = ImageFont.truetype(FONT, round(height * 0.62))
    axes = {a["name"]: a for a in font.get_variation_axes()}
    font.set_variation_by_axes([900 if n == b"Weight" else a["default"] for n, a in axes.items()])
    text = "SuperLM"
    left, top, right, bottom = font.getbbox(text)
    gap = round(height * 0.28)
    canvas = Image.new("RGBA", (height + gap + right - left, height), (0, 0, 0, 0))
    canvas.alpha_composite(tile(icon, height))
    ImageDraw.Draw(canvas).text(
        (height + gap - left, (height - (bottom - top)) / 2 - top), text, font=font, fill=ink
    )
    return canvas


def main(icon_path: str, out_dir: str) -> None:
    icon = Image.open(icon_path).convert("RGBA")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tile(icon, 256).save(out / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    tile(icon, 32).save(out / "favicon-32.png")
    tile(icon, 192).save(out / "icon-192.png")
    tile(icon, 512).save(out / "icon-512.png")
    # iOS fills transparency with black and rounds the corners itself.
    touch = Image.new("RGBA", (180, 180), (255, 255, 255, 255))
    touch.alpha_composite(tile(icon, 180))
    touch.convert("RGB").save(out / "apple-touch-icon.png")
    icon.resize((1024, 1024), Image.LANCZOS).save(out / "logo.png")
    for scheme, ink in INK.items():
        wordmark(icon, ink).save(out / f"logo-wordmark-{scheme}.png")


if __name__ == "__main__":
    main(*sys.argv[1:3])
