#!/usr/bin/env python3
"""Render the harvest festival banner's English once to src/font/festival-banner.png (96 x 32, black ink on white),
the mask 45-festival-banner.py draws into the banner's tiles. One-shot: refuses to overwrite the PNG (it may have
been touched up by hand); pass --force to redo it.

    python3 -I tools/gfx/make_banner.py [--force]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[2] / 'src' / 'font' / 'festival-banner.png'
FONT = '/usr/share/fonts/google-crosextra-caladea-fonts/Caladea-Bold.ttf'
LINES, SIZE, W, H = ['Harvest', 'Festival'], 21, 96, 32  # 14 px a line: neither word has a descender


def main() -> None:
    if OUT.exists() and '--force' not in sys.argv:
        raise SystemExit(f'{OUT} exists (hand-edited?); --force to overwrite')
    font = ImageFont.truetype(FONT, SIZE)
    im = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(im)
    for i, text in enumerate(LINES):
        top = d.textbbox((0, 0), text, font=font)[1]
        d.text(((W - d.textlength(text, font=font)) / 2, i * 16 + 1 - top), text, font=font, fill=255)
    im.point(lambda v: 0 if v >= 110 else 255).convert('1').save(OUT)
    print(f'wrote {OUT}')


if __name__ == '__main__':
    main()
