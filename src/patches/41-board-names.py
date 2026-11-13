"""The rivals' names on the harvest festival results boards (Miss Contest, Cooking, Arts, Tournament) in English.

Each name is its own compressed image in the asset table at C9 `$0000` (entries `$0486`-`$04DD`, one per rival, 1 KiB:
16 x 2 tiles of 4bpp, row-major, a 128 x 16 px strip, ink colour 1 on 0). The board loads three of them into VRAM
`$0000`-`$05FF` when it shows the places. This module draws each English name from
src/font/en-vwf.png centred in the 80 px the board shows and stores it raw (format 0, `$80:A30C`) at GFX4, repointing the entry.
Entry `$0483` is the board's digit sheet and `$04E0` a blank strip (the daughter's slot): both left alone.
"""

import json

from PIL import Image

from _layout import FONT_FIRST, GFX4, REPO, put, snes_to_rom

ASSET_TABLE = 0xC90000
INK = 1
W, H = 128, 16
SHOWN = 80  # the board shows the strip's first 80 px (the Japanese names, 12 px kana, fit in it)
RAISE = 2  # the font's cap height sits lower than the kana's: drawn 2 px up

NAMES = {  # asset table offset: English (tools/text/glossary.tsv)
    0x486: 'Rosalie', 0x489: 'Leon', 0x48C: 'Lianne', 0x48F: 'Medinia', 0x492: 'Jogja', 0x495: 'Bathurst',
    0x498: 'Legion', 0x49B: 'Yuri', 0x49E: 'Pugachev', 0x4A1: 'Negros', 0x4A4: 'Martha', 0x4A7: 'Marie',
    0x4AA: 'Bathia', 0x4AD: 'Leila', 0x4B0: 'Catherine', 0x4B3: 'Mary', 0x4B6: 'Eiriel', 0x4B9: 'Fanran',
    0x4BC: 'Laszlo', 0x4BF: 'Raja', 0x4C2: 'Martin', 0x4C5: 'Merry', 0x4C8: 'Roxanne', 0x4CB: 'Lily',
    0x4CE: 'Santa', 0x4D1: 'Norfolk', 0x4D4: 'Milan', 0x4D7: 'Andrew', 0x4DA: 'Farant', 0x4DD: 'Boussant',
}


def font() -> tuple[dict[str, list[int]], dict[str, int]]:
    meta = json.loads((REPO / 'src' / 'font' / 'en-vwf.json').read_text())
    img = Image.open(REPO / 'src' / 'font' / 'en-vwf.png').convert('1')
    cw, ch = meta['cell']
    glyphs = {}
    for i in range(96):
        x0, y0 = (i % 16) * cw, (i // 16) * ch
        glyphs[chr(FONT_FIRST + i)] = [sum(0x80 >> x for x in range(cw) if img.getpixel((x0 + x, y0 + y)) == 0)
                                       for y in range(ch)]
    return glyphs, meta['widths']


def strip(text: str, glyphs: dict[str, list[int]], widths: dict[str, int]) -> bytes:
    width = sum(widths.get(c, 0) for c in text)
    if width > SHOWN:
        raise SystemExit(f"board name '{text}' is {width} px, the board shows {SHOWN}")
    px = [[0] * W for _ in range(H)]
    x = (SHOWN - width) // 2
    for c in text:
        for y in range(RAISE, H):
            for gx in range(8):
                if glyphs[c][y] & 0x80 >> gx and x + gx < W:
                    px[y - RAISE][x + gx] = INK
        x += widths.get(c, 0)
    out = bytearray(32 * 32)
    for t in range(32):
        tx, ty = t % 16, t // 16
        for y in range(8):
            for xx in range(8):
                v = px[ty * 8 + y][tx * 8 + xx]
                for plane in range(4):
                    if v >> plane & 1:
                        out[t * 32 + (plane >> 1) * 16 + y * 2 + (plane & 1)] |= 0x80 >> xx
    return bytes(out)


def apply(rom: bytearray) -> None:
    glyphs, widths = font()
    at = GFX4
    for entry, text in NAMES.items():
        o = snes_to_rom(ASSET_TABLE + entry)
        src = snes_to_rom(int.from_bytes(rom[o:o + 3], 'little'))
        if rom[src] & 0x0F not in (2, 4) or int.from_bytes(rom[src + 1:src + 3], 'little') != 0x400:
            raise SystemExit(f'C9:{entry:04X}: not a 1 KiB name strip (format {rom[src]:02X})')
        blob = bytes([0xA0]) + (0x400).to_bytes(2, 'little') + strip(text, glyphs, widths)
        put(rom, at, blob)
        rom[o:o + 3] = at.to_bytes(3, 'little')
        at += len(blob)
    print(f'  board names: {len(NAMES)} in English at ${GFX4:06X}')
