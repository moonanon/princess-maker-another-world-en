#!/usr/bin/env python3
"""The Japanese ROM's 16x16 text font as contact sheets, each glyph labelled by its text code -> build/font/.

    python3 -I tools/text/jp_font.py [--from CODE] [--to CODE] [--scale N]

The font is bank $DD: 1bpp 16x16 glyphs of 32 bytes, four 8x8 tiles (top-left, top-right, bottom-left,
bottom-right) of 8 bytes each. A one-byte code c ($08-$CF) is glyph c - $08; a two-byte code c ($0400 up)
is glyph c - $338 (so $0400 follows $CF). $D0-$3FF are control codes and have no glyph.
Each sheet is 16 x 16 glyphs; the label left of a row is
the code of its first glyph and the column header the offset from it.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rom'))
from RomExtract import REPO, rom, snes_to_rom  # noqa: E402

FONT = 0xDD0000
GLYPHS = 0x10000 // 32
OUT = REPO / 'build' / 'font'
CELL = 20
LABEL = 40


def codes():
    """Every glyph's text code, in font order."""
    yield from range(0x08, 0xD0)
    yield from range(0x400, 0x338 + GLYPHS)


def glyph_offset(code: int) -> int:
    return snes_to_rom(FONT) + ((code - 0x08) if code < 0xD0 else (code - 0x338)) * 32


def draw(data: bytes, code: int) -> Image.Image:
    im = Image.new('L', (16, 16), 255)
    at = glyph_offset(code)
    for tile, (tx, ty) in enumerate(((0, 0), (1, 0), (0, 1), (1, 1))):
        for row in range(8):
            bits = data[at + tile * 8 + row]
            for col in range(8):
                if bits >> (7 - col) & 1:
                    im.putpixel((tx * 8 + col, ty * 8 + row), 0)
    return im


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--from', dest='lo', type=lambda s: int(s, 16), default=0x08)
    ap.add_argument('--to', dest='hi', type=lambda s: int(s, 16), default=0xB37)
    ap.add_argument('--scale', type=int, default=2)
    args = ap.parse_args()
    data = rom()
    chosen = [c for c in codes() if args.lo <= c <= args.hi]
    OUT.mkdir(parents=True, exist_ok=True)
    for page in range(0, len(chosen), 256):
        part = chosen[page : page + 256]
        rows = (len(part) + 15) // 16
        sheet = Image.new('L', (LABEL + 16 * CELL, rows * CELL + 12), 255)
        pen = ImageDraw.Draw(sheet)
        for col in range(16):
            pen.text((LABEL + col * CELL + 4, 0), f'{col:X}', fill=128)
        for i, code in enumerate(part):
            r, c = divmod(i, 16)
            if c == 0:
                pen.text((0, 12 + r * CELL + 4), f'{code:03X}', fill=128)
            sheet.paste(draw(data, code), (LABEL + c * CELL + 2, 12 + r * CELL + 2))
        path = OUT / f'font-{part[0]:03X}-{part[-1]:03X}.png'
        sheet.resize((sheet.width * args.scale, sheet.height * args.scale), Image.NEAREST).save(path)
        print(path.relative_to(REPO))


if __name__ == '__main__':
    main()
