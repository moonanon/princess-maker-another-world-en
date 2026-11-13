"""The harvest festival results board's labels in English: 1st / 2nd / 3rd place -> 1st / 2nd / 3rd, points -> pts, and the
tournament board's runner-up -> Runner-up.

The board is BG tiles CE `$8B4B` (asset table C9 `$03A8`, LZ4, 256 tiles) and tilemap D0 `$230C` (C9 `$0513`, LZ4,
32 x 32). Every tile number is used by one of the screen's maps, so the labels are
redrawn in place: the 2 x 2 tiles of the winner glyph, of 2 and of 3 become 1st / 2nd / 3rd, the 2 x 2 tiles of
the points glyph becomes pts, and the map cells of the other two glyphs are set to the box's background tile. The crown between them stays.
Both are stored raw (format 0, `$80:A30C`) after 41-board-names.py's strips at GFX4 and the table entries repointed.
"""

import json

from PIL import Image

from _layout import FONT_FIRST, GFX4, REPO, put, snes_to_rom
from _narrow import NARROW, narrow_rows

import sys
sys.path.insert(0, str(REPO / 'tools' / 'gfx'))
from lz import decompress  # noqa: E402

AT = GFX4 + 0x8000  # 41-board-names.py uses 30 x 0x403 bytes from GFX4
TILES_ENTRY, TILES = 0xC903A8, 0xCE8B4B
MAP_ENTRY, MAP = 0xC90513, 0xD0230C
BG = 0x02E  # the boxes' background tile
PLACE_INK, PLACE_SHADOW = 14, 11  # the kanji's own brightest and darkest shade
PTS_INK, PTS_SHADOW = 15, 11

LABELS = [  # (top row tiles, bottom row tiles), English, ink, shadow
    ((0x00D, 0x00E), (0x01D, 0x01E), '1st', PLACE_INK, PLACE_SHADOW),
    ((0x04A, 0x04B), (0x05A, 0x05B), '2nd', PLACE_INK, PLACE_SHADOW),
    ((0x04C, 0x04D), (0x05C, 0x05D), '3rd', PLACE_INK, PLACE_SHADOW),
    ((0x06A, 0x06B), (0x07A, 0x07B), 'pts', PTS_INK, PTS_SHADOW),
    (tuple(range(0x090, 0x097)), tuple(range(0x0A0, 0x0A7)), 'Runner-up', PLACE_INK, PLACE_SHADOW),  # runner-up (tournament)
]
BLANKED = {0x00F, 0x02F, 0x01F, 0x03F, 0x04E, 0x04F, 0x05E, 0x05F}  # those two glyphs: map cells set to BG
CLEARED = (0x00F, 0x02F, 0x01F, 0x03F)  # the first one's tiles drawn as background too: the tournament board's map (CE `$9C8C`) uses them


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


def tile_px(chr_data: bytes | bytearray, t: int) -> list[list[int]]:
    b = t * 32
    return [[sum((chr_data[b + (p >> 1) * 16 + y * 2 + (p & 1)] >> (7 - x) & 1) << p for p in range(4))
             for x in range(8)] for y in range(8)]


def px_tile(px: list[list[int]]) -> bytes:
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            for p in range(4):
                if px[y][x] >> p & 1:
                    out[(p >> 1) * 16 + y * 2 + (p & 1)] |= 0x80 >> x
    return bytes(out)


def draw(text: str, glyphs: dict[str, list[int]], widths: dict[str, int], W: int = 16) -> list[list[bool]]:
    """W x 16 ink mask, centred; lower case narrowed (_narrow.py) when the font's is too wide."""
    def run(narrow: bool) -> tuple[list[tuple[list[int], int]], int]:
        cells = [(narrow_rows(c)[0], narrow_rows(c)[1] + 1) if narrow and c in NARROW else (glyphs[c], widths[c])
                 for c in text]
        return cells, sum(a for _, a in cells) - 1  # no gap after the last letter
    cells, w = run(False)
    if w > W - 1:
        cells, w = run(True)
    if w > W - 1:
        raise SystemExit(f"board label '{text}' is {w} px, the cells are {W} (with its shadow)")
    ink = [[False] * W for _ in range(16)]
    x = (W - 1 - w) // 2
    for rows, adv in cells:
        for y in range(16):
            for gx in range(8):
                if rows[y] & 0x80 >> gx and 0 <= x + gx < W:
                    ink[y][x + gx] = True
        x += adv
    return ink


def apply(rom: bytearray) -> None:
    for entry, addr in ((TILES_ENTRY, TILES), (MAP_ENTRY, MAP)):
        o = snes_to_rom(entry)
        if int.from_bytes(rom[o:o + 3], 'little') != addr:
            raise SystemExit(f"${entry:06X} doesn't point at ${addr:06X} (the results board)")
    glyphs, widths = font()
    chr_data = bytearray(decompress(rom, snes_to_rom(TILES) + 1)[0])
    tmap = bytearray(decompress(rom, snes_to_rom(MAP) + 1)[0])
    bg = tile_px(chr_data, BG)
    for t in CLEARED:
        chr_data[t * 32:t * 32 + 32] = px_tile(bg)
    for top, bottom, text, ink_c, shadow_c in LABELS:
        ink = draw(text, glyphs, widths, len(top) * 8)
        for i, t in enumerate(top + bottom):
            ox, oy = (i % len(top)) * 8, (i // len(top)) * 8
            px = [[bg[y][x] for x in range(8)] for y in range(8)]
            for y in range(8):
                for x in range(8):
                    gy, gx = oy + y, ox + x
                    if ink[gy][gx]:
                        px[y][x] = ink_c
                    elif (gx and ink[gy][gx - 1]) or (gy and ink[gy - 1][gx]) or (gx and gy and ink[gy - 1][gx - 1]):
                        px[y][x] = shadow_c
            chr_data[t * 32:t * 32 + 32] = px_tile(px)
    blanked = 0
    for i in range(0, len(tmap), 2):
        e = tmap[i] | tmap[i + 1] << 8
        if e & 0x3FF in BLANKED:
            e = e & ~0xC3FF | BG  # no flip: the background tile is symmetric anyway
            tmap[i:i + 2] = e.to_bytes(2, 'little')
            blanked += 1
    at = AT
    for entry, data in ((TILES_ENTRY, chr_data), (MAP_ENTRY, tmap)):
        blob = bytes([0xA0]) + len(data).to_bytes(2, 'little') + bytes(data)
        put(rom, at, blob)
        o = snes_to_rom(entry)
        rom[o:o + 3] = at.to_bytes(3, 'little')
        at += len(blob)
    print(f'  board labels: {len(LABELS)} redrawn, {blanked} cells blanked')
