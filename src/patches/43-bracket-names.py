"""The harvest festival tournament bracket's fighter names in English.

The bracket's tiles are CF `$52A1` (asset table C9 `$0477`, LZ4, 256 tiles 4bpp); each fighter's name is pre-drawn in
one row of 5 tiles (40 x 8 px, ink colour 1): tile rows 2-7 at columns 8-12 and rows 3-7 at columns 0-4. This module clears those tiles and draws the English in the 5x7 font of 19-status-name.py, spaced
by each letter's own width (1 px apart, none when the name is still too wide), and stores the sheet raw (format 0)
after 42-board-labels.py's data at GFX4, repointing the entry.
"""

import importlib.util
from pathlib import Path

from _layout import GFX4, REPO, put, snes_to_rom

import sys
sys.path.insert(0, str(REPO / 'tools' / 'gfx'))
from lz import decompress  # noqa: E402

AT = GFX4 + 0xB000  # after 42-board-labels.py (GFX4 + 0x8000, 0x2803 + 0x803 bytes); two sheets, 0x2003 + 0x1003
SHEETS = [  # (asset table entry, tiles, {(tile row, first column): English})
    (0xC90477, 0xCF52A1, {
        (2, 8): 'Rosalie', (3, 8): 'Lianne', (4, 8): 'Jogja', (5, 8): 'Legion', (6, 8): 'Pugachev', (7, 8): 'Martha',
        (3, 0): 'Leon', (4, 0): 'Medinia', (5, 0): 'Bathurst', (6, 0): 'Yuri', (7, 0): 'Negros'}),
    (0xC9047A, 0xCF5461, {(0, 0): 'Marie'}),  # the twelfth fighter, in the bracket's second tile set
]
INK = 1
W = 40


def small_font() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location('sn', Path(__file__).with_name('19-status-name.py'))
    sn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sn)
    return sn.FONT


def strip(text: str, font: dict[str, str]) -> list[list[int]]:
    glyphs = []
    for c in text:
        rows = font[c].split('|')
        cols = [x for x in range(5) if any(r[x] == '#' for r in rows)]
        glyphs.append((rows, min(cols), max(cols) - min(cols) + 1))
    for gap in (1, 0):
        width = sum(w for _, _, w in glyphs) + gap * (len(glyphs) - 1)
        if width <= W:
            break
    else:
        raise SystemExit(f"bracket name '{text}' is {width} px, the room is {W}")
    px = [[0] * W for _ in range(8)]
    x = (W - width) // 2
    for rows, x0, w in glyphs:
        for y, r in enumerate(rows):
            for gx in range(w):
                if r[x0 + gx] == '#':
                    px[y][x + gx] = INK
        x += w + gap
    return px


def px_tile(px: list[list[int]], ox: int) -> bytes:
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            for p in range(4):
                if px[y][ox + x] >> p & 1:
                    out[(p >> 1) * 16 + y * 2 + (p & 1)] |= 0x80 >> x
    return bytes(out)


def apply(rom: bytearray) -> None:
    font = small_font()
    at, count = AT, 0
    for entry, tiles, names in SHEETS:
        o = snes_to_rom(entry)
        if int.from_bytes(rom[o:o + 3], 'little') != tiles:
            raise SystemExit(f"${entry:06X} doesn't point at ${tiles:06X} (the tournament bracket)")
        chr_data = bytearray(decompress(rom, snes_to_rom(tiles) + 1)[0])
        for (row, col), text in names.items():
            px = strip(text, font)
            for i in range(5):
                t = row * 32 + col + i
                chr_data[t * 32:t * 32 + 32] = px_tile(px, i * 8)
            count += 1
        blob = bytes([0xA0]) + len(chr_data).to_bytes(2, 'little') + bytes(chr_data)
        put(rom, at, blob)
        rom[o:o + 3] = at.to_bytes(3, 'little')
        at += len(blob)
    print(f'  bracket names: {count} in English')
