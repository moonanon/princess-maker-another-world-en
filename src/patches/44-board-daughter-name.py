"""The daughter's name on the harvest festival results board in Latin letters.

The board draws her name (`7E:0EE8`, 8 name codes) at `83:D6CB`: each code is looked up in the 93-entry table at
C7 `$03BD` (`88:8C87`, index 0 = blank) and the glyph at that index (0x40 bytes: an 8 x 16 glyph, top tile then bottom
tile, 4bpp) is copied from the katakana sheet CF `$58B2` (asset table C9 `$0480`, LZ4), decompressed to `$7F:0000`.
The English name grid stores Latin letters as kana codes (15-vwf.py `name_map`, table at NAME_MAP), so this module
redraws, for every code the name map turns into a letter, that code's glyph in the sheet as the letter (src/font/
en-vwf.png, in the sheet's own ink), and stores the sheet raw (format 0) at GFX4 + 0xE100, repointing the entry.

"""

import json
from collections import Counter

from PIL import Image

import importlib.util
from pathlib import Path

from _layout import FONT_FIRST, GFX4, GFX5, NAME_MAP, REPO, put, snes_to_rom

import sys
sys.path.insert(0, str(REPO / 'tools' / 'gfx'))
from lz import decompress  # noqa: E402

AT = GFX4 + 0xE100  # after 43-bracket-names.py (GFX4 + 0xB000, 0x2003 + 0x1003 bytes)
ENTRY, SHEET = 0xC90480, 0xCF58B2
CODES = 0xC703BD  # code of each glyph index (93)
SMALL_ENTRY, SMALL = 0xC9047D, 0xCF55B0  # the bracket's 8x8 font: glyph i at i * 32 (glyph 0 blank), 2bpp,
#                                          the top tile empty and the letter in the bottom tile, ink colour 1


def small_font() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location('sn', Path(__file__).with_name('19-status-name.py'))
    sn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sn)
    return sn.FONT


def small_sheet(rom: bytearray, name_map: bytes, codes: bytes) -> int:
    o = snes_to_rom(SMALL_ENTRY)
    if int.from_bytes(rom[o:o + 3], 'little') != SMALL:
        raise SystemExit(f"${SMALL_ENTRY:06X} doesn't point at ${SMALL:06X} (the bracket's 8x8 font)")
    sheet = bytearray(decompress(rom, snes_to_rom(SMALL) + 1)[0])
    font = small_font()
    drawn = 0
    for i, code in enumerate(codes):
        ch = chr(name_map[code]) if i and name_map[code] else ''
        if ch not in font or (i + 1) * 32 > len(sheet):
            continue
        rows = font[ch].split('|')
        g = bytearray(32)
        for y, r in enumerate(rows[:8]):
            g[16 + y * 2] = sum(0x80 >> (x + 1) for x, c in enumerate(r) if c == '#')  # bottom tile, plane 0
        sheet[i * 32:(i + 1) * 32] = g
        drawn += 1
    blob = bytes([0xA0]) + len(sheet).to_bytes(2, 'little') + bytes(sheet)
    put(rom, GFX5, blob)
    rom[o:o + 3] = GFX5.to_bytes(3, 'little')
    return drawn


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


def tile(px: list[list[int]]) -> bytes:
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            for p in range(4):
                if px[y][x] >> p & 1:
                    out[(p >> 1) * 16 + y * 2 + (p & 1)] |= 0x80 >> x
    return bytes(out)


def apply(rom: bytearray) -> None:
    o = snes_to_rom(ENTRY)
    if int.from_bytes(rom[o:o + 3], 'little') != SHEET:
        raise SystemExit(f"${ENTRY:06X} doesn't point at ${SHEET:06X} (the board's katakana sheet)")
    sheet = bytearray(decompress(rom, snes_to_rom(SHEET) + 1)[0])
    ink = Counter()
    for t in range(len(sheet) // 32):
        for y in range(8):
            for x in range(8):
                v = sum((sheet[t * 32 + (p >> 1) * 16 + y * 2 + (p & 1)] >> (7 - x) & 1) << p for p in range(4))
                if v:
                    ink[v] += 1
    colour = ink.most_common(1)[0][0]
    glyphs, widths = font()
    name_map = rom[snes_to_rom(NAME_MAP):snes_to_rom(NAME_MAP) + 256]
    codes = rom[snes_to_rom(CODES):snes_to_rom(CODES) + 93]
    drawn = 0
    for i, code in enumerate(codes):
        ch = chr(name_map[code]) if i and name_map[code] else ''
        if not ch or ch not in glyphs or (i + 1) * 0x40 > len(sheet):
            continue
        w = widths.get(ch, 0)
        x0 = max(0, (8 - w) // 2)
        px = [[colour if x >= x0 and glyphs[ch][y] & 0x80 >> (x - x0) else 0 for x in range(8)] for y in range(16)]
        sheet[i * 0x40:i * 0x40 + 0x20] = tile(px[:8])
        sheet[i * 0x40 + 0x20:i * 0x40 + 0x40] = tile(px[8:])
        drawn += 1
    blob = bytes([0xA0]) + len(sheet).to_bytes(2, 'little') + bytes(sheet)
    put(rom, AT, blob)
    rom[o:o + 3] = AT.to_bytes(3, 'little')
    small = small_sheet(rom, name_map, codes)
    print(f'  board daughter name: {drawn} glyphs as Latin letters (ink {colour}); bracket font {small}')
