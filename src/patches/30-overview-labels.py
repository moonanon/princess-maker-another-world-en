"""The status overview's labels in English (both pages): they are pre-drawn into the screen's BG1 tiles, not text.

Each page loads its BG1 tiles and tilemap (28 rows x 32), LZ format 3 or 4, through the asset pointer table at
C9 `$0000`. This module decompresses both (tools/gfx/lz.py), clears every label's cells
to the box's two background tiles, draws the English from src/font/en-vwf.png in the labels' own colours (ink 15,
shadow 11, one pixel right and down), gives the new cells free tile numbers (any of 0-255 the new map doesn't use),
and stores tiles and map as raw assets (format 0, `$80:A30C`) in the expanded ROM, repointing the two table entries.
A label is (top row, first column, last column it may use, English); the last column keeps clear of the value the
game prints beside it. English '' just clears (pre-drawn units like blood-type and age after a value).
"""

import json
import sys

from PIL import Image

from _layout import FONT_FIRST, GFX, REPO, put, snes_to_rom
from _narrow import NARROW, TINY, narrow_rows, tiny_rows

sys.path.insert(0, str(REPO / 'tools' / 'gfx'))
from lz import decompress, decompress3  # noqa: E402

ASSET_TABLE = 0xC90000
INK, SHADOW = 15, 11

PAGES = [
    {'what': 'overview page 1 (stats)', 'tiles_entry': 0xC9037E, 'tiles': 0xCE1314, 'map_entry': 0xC90384,
     'map': 0xCE28AC, 'blank': (0x019, 0x022), 'labels': [
         (2, 2, 6, 'Vigor'), (4, 2, 6, 'Might'), (6, 2, 6, 'Intellect'), (8, 2, 6, 'Grace'), (10, 2, 6, 'Charm'),
         (12, 2, 6, 'Morality'), (14, 2, 6, 'Faith'), (16, 2, 6, 'Sin'), (18, 2, 6, 'Sensitivity'), (20, 2, 6, 'Stress'),
         (11, 12, 18, 'Warrior'), (11, 21, 28, 'Magic'), (13, 12, 18, 'Social'), (13, 21, 28, 'Domestic'),
         (16, 12, 18, 'Etiquette'), (16, 21, 28, 'Cooking'), (18, 12, 18, 'Art'), (18, 21, 28, 'Cleaning'),
         (20, 12, 18, 'Speech'), (20, 21, 26, 'Temperance'),
         (23, 2, 9, 'Combat'), (23, 13, 17, 'Attack'), (23, 22, 27, 'Defense'),
         (25, 2, 9, 'Sorcery'), (25, 13, 17, 'Mana'), (25, 22, 27, 'Magic Def.')]},
    {'what': 'overview page 2 (profile)', 'tiles_entry': 0xC90387, 'tiles': 0xCE2C5D, 'map_entry': 0xC9038A,
     'map': 0xCE357C, 'blank': (0x00E, 0x018), 'labels': [
         (6, 2, 12, 'Blood Type'), (6, 14, 15, ''), (8, 2, 12, 'Age'), (8, 14, 15, ''), (10, 2, 8, 'Born'),
         (12, 2, 8, 'Sign'), (14, 2, 8, 'Patron'),
         (2, 18, 22, 'Height'), (4, 18, 22, 'Weight'), (6, 18, 22, 'Bust'), (8, 18, 23, 'Waist'),
         (10, 18, 22, 'Hips'), (14, 18, 25, 'Illness'), (18, 18, 25, 'Delinquency'), (22, 18, 25, 'Popularity'),
         (24, 18, 20, 'Diet')]},
]


def font() -> tuple[dict[str, list[int]], dict[str, int]]:
    meta = json.loads((REPO / 'src' / 'font' / 'en-vwf.json').read_text())
    img = Image.open(REPO / 'src' / 'font' / 'en-vwf.png').convert('1')
    cw, ch = meta['cell']
    glyphs = {}
    for i in range(96):
        c = chr(FONT_FIRST + i)
        x0, y0 = (i % 16) * cw, (i // 16) * ch
        glyphs[c] = [sum(0x80 >> x for x in range(cw) if img.getpixel((x0 + x, y0 + y)) == 0) for y in range(ch)]
    return glyphs, meta['widths']


def tile_px(chr_data: bytes | bytearray, t: int) -> list[list[int]]:
    b = t * 32
    return [[(chr_data[b + y * 2] >> (7 - x) & 1) | (chr_data[b + y * 2 + 1] >> (7 - x) & 1) << 1 |
             (chr_data[b + 16 + y * 2] >> (7 - x) & 1) << 2 | (chr_data[b + 17 + y * 2] >> (7 - x) & 1) << 3
             for x in range(8)] for y in range(8)]


def px_tile(px: list[list[int]]) -> bytes:
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            v = px[y][x]
            for plane in range(4):
                if v >> plane & 1:
                    out[(plane >> 1) * 16 + y * 2 + (plane & 1)] |= 0x80 >> x
    return bytes(out)


def asset(rom: bytearray, addr: int) -> bytes:
    o = snes_to_rom(addr)
    fmt = rom[o] & 0x0F
    if fmt not in (3, 4):
        raise SystemExit(f'${addr:06X}: format {rom[o]:02X}, not LZ 3/4')
    return (decompress if fmt == 4 else decompress3)(rom, o + 1)[0]


def apply(rom: bytearray) -> None:
    glyphs, widths = font()
    at = GFX
    for page in PAGES:
        for entry, addr in ((page['tiles_entry'], page['tiles']), (page['map_entry'], page['map'])):
            o = snes_to_rom(entry)
            if int.from_bytes(rom[o:o + 3], 'little') != addr:
                raise SystemExit(f"${entry:06X} doesn't point at ${addr:06X} ({page['what']})")
        chr_data = bytearray(asset(rom, page['tiles']))
        tmap = bytearray(asset(rom, page['map']))
        top, bottom = page['blank']

        def cell(r: int, c: int) -> int:
            return tmap[(r * 32 + c) * 2] | tmap[(r * 32 + c) * 2 + 1] << 8

        def set_cell(r: int, c: int, tile: int) -> None:
            e = cell(r, c) & ~0x3FF | tile
            tmap[(r * 32 + c) * 2:(r * 32 + c) * 2 + 2] = e.to_bytes(2, 'little')

        drawn = []
        for row, c0, c1, text in page['labels']:
            for r, blank in ((row, top), (row + 1, bottom)):
                for c in range(c0, c1 + 1):
                    set_cell(r, c, blank)
            if not text:
                continue
            w = (c1 - c0 + 1) * 8
            def glyph(ch: str, mode: int) -> tuple[list[int], int]:
                if mode == 2 and ch in TINY:
                    g, adv = tiny_rows(ch)
                    return g, adv + 1
                if mode >= 1 and ch in NARROW:
                    g, adv = narrow_rows(ch)
                    return g, adv + 1
                return glyphs[ch], widths.get(ch, 0)

            mode = 2  # every label in the tiny set (_narrow.py), so they all match
            img = [[None] * w for _ in range(16)]
            x = 1
            for ch in text:
                if mode:
                    g, adv = glyph(ch, mode)
                else:
                    g, adv = glyphs[ch], widths.get(ch, 0)
                for y in range(16):
                    for gx in range(8):
                        if g[y] & 0x80 >> gx and x + gx < w and y + 1 < 16:
                            img[y + 1][x + gx] = INK
                x += adv
            if x > w + 1:
                raise SystemExit(f"'{text}' is {x} px, the space is {w} ({page['what']})")
            for y in range(16):
                for xx in range(w):
                    if img[y][xx] == INK:
                        for sy, sx in ((y, xx + 1), (y + 1, xx), (y + 1, xx + 1)):
                            if sy < 16 and sx < w and img[sy][sx] is None:
                                img[sy][sx] = SHADOW
            drawn.append((row, c0, c1, img))
        used = {cell(r, c) & 0x3FF for r in range(28) for c in range(32)}
        free = [t for t in range(256) if t not in used]
        for row, c0, c1, img in drawn:
            for half, r, blank in ((0, row, top), (1, row + 1, bottom)):
                base = tile_px(chr_data, blank)
                for c in range(c0, c1 + 1):
                    px = [[img[half * 8 + y][(c - c0) * 8 + x] if img[half * 8 + y][(c - c0) * 8 + x] is not None
                           else base[y][x] for x in range(8)] for y in range(8)]
                    if px == base:
                        continue
                    if not free:
                        raise SystemExit(f"out of free tiles ({page['what']})")
                    t = free.pop(0)
                    chr_data[t * 32:t * 32 + 32] = px_tile(px)
                    set_cell(r, c, t)
        for entry, data in ((page['tiles_entry'], chr_data), (page['map_entry'], tmap)):
            blob = bytes([0xA0]) + len(data).to_bytes(2, 'little') + bytes(data)
            if (at & 0xFFFF) + len(blob) > 0x10000:
                at = (at & 0xFF0000) + 0x10000
            put(rom, at, blob)
            o = snes_to_rom(entry)
            rom[o:o + 3] = at.to_bytes(3, 'little')
            at += len(blob)
        print(f"  {page['what']}: {len(drawn)} labels, {len(free)} tiles left")
