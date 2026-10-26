"""Makes the SuperLM favicon and logos in brand/ from the notifier icon.

The icon is drawn once, by make_icon.swift; this only crops, scales and lays it out,
so the favicon, the logos and the notification banner stay one picture.

    swift tools/notifier/make_icon.swift /tmp/icon.png
    python3 tools/notifier/make_brand.py /tmp/icon.png brand/

Each app gets the same picture with its own letter and gradient (APPS), in brand/<app>/:

    python3 tools/notifier/make_brand.py --app tradelm brand/tradelm/

Needs Pillow and the macOS system font (SF Pro) for the wordmark.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# The rounded tile sits at 100..924 of 1024 in the icon (make_icon.swift).
TILE = (100 / 1024, 924 / 1024)
FONT = "/System/Library/Fonts/SFNS.ttf"
INK = {"light": (24, 20, 38, 255), "dark": (255, 255, 255, 255)}
# (owner) One row per app: wordmark, tile letter, gradient top-left -> bottom-right.
# Hues stay apart from each other and from the green spark; a new app adds a row here.
APPS = {
    "tradelm": ("TradeLM", "T", "3f73fa", "5a3fd9"),
    "authorlm": ("AuthorLM", "A", "f9b233", "eb5a2a"),
    "corpuslm": ("CorpusLM", "C", "f0508c", "c42a4a"),
    "mailerlm": ("MailerLM", "M", "12bfe6", "1e6fe0"),
    "supplylm": ("SupplyLM", "S", "4a5670", "1c2233"),
    "publishinglm": ("PublishingLM", "P", "7c3aed", "4c1d95"),
    "computerlm": ("ComputerLM", "K", "0f9d8a", "0b5f6b"),
    "gamelm": ("GameLM", "G", "d946ef", "86198f"),
    "peoplelm": ("PeopleLM", "H", "c2773a", "7a3e1d"),
}


def tile(icon: Image.Image, size: int) -> Image.Image:
    lo, hi = (round(f * icon.width) for f in TILE)
    return icon.crop((lo, lo, hi, hi)).resize((size, size), Image.LANCZOS)


def wordmark(icon: Image.Image, ink: tuple, text: str = "SuperLM", height: int = 256) -> Image.Image:
    font = ImageFont.truetype(FONT, round(height * 0.62))
    axes = {a["name"]: a for a in font.get_variation_axes()}
    font.set_variation_by_axes([900 if n == b"Weight" else a["default"] for n, a in axes.items()])
    left, top, right, bottom = font.getbbox(text)
    gap = round(height * 0.28)
    canvas = Image.new("RGBA", (height + gap + right - left, height), (0, 0, 0, 0))
    canvas.alpha_composite(tile(icon, height))
    ImageDraw.Draw(canvas).text((height + gap - left, (height - (bottom - top)) / 2 - top), text, font=font, fill=ink)
    return canvas


def main(icon_path: str, out_dir: str, name: str = "SuperLM") -> None:
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
        wordmark(icon, ink, name).save(out / f"logo-wordmark-{scheme}.png")


def app(key: str, out_dir: str) -> None:
    name, letter, start, end = APPS[key]
    with tempfile.TemporaryDirectory() as tmp:
        icon = f"{tmp}/icon.png"
        swift = Path(__file__).with_name("make_icon.swift")
        subprocess.run(["swift", str(swift), icon, letter, start, end], check=True)
        main(icon, out_dir, name)


if __name__ == "__main__":
    if sys.argv[1] == "--app":
        app(*sys.argv[2:4])
    else:
        main(*sys.argv[1:3])
