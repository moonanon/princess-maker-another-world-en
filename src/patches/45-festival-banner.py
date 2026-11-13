"""The harvest festival's harvest-festival banner in English ("Harvest" over "Festival").

The festival screens' background is tiles CE `$9DBC` (asset table C9 `$03B4`, nibble codec, 256 tiles) and maps
CE `$B028` (C9 `$03B7`) and CE `$B48B` (C9 `$03BA`), LZ4. The banner's inside is 16 x 4
cells: three kanji of 4 x 4 tiles (`$01`-`$0C`, `$11`-`$1C`, `$21`-`$2C`, `$31`-`$3C`) with the plain tile `$10` in the
two gaps. This module puts `$10` in the inside's two outer columns on each side and the 48 kanji tiles, in order, in
the middle 12 (96 x 32 px), and redraws those tiles as the English from src/font/festival-banner.png (a serif rendered once by
tools/gfx/make_banner.py), bevelled in the kanji's own colours. Sheet and maps are stored raw (format 0) at GFX5 + 0x1000.
"""

from PIL import Image

from _layout import GFX5, REPO, put, snes_to_rom

import sys
sys.path.insert(0, str(REPO / 'tools' / 'gfx'))
from lz import decompress, decompress2  # noqa: E402

AT = GFX5 + 0x1000  # after 44-board-daughter-name.py's 8x8 font (0xC03 bytes at GFX5)
TILES_ENTRY, TILES = 0xC903B4, 0xCE9DBC
MAPS = [(0xC903B7, 0xCEB028), (0xC903BA, 0xCEB48B)]
PLAIN = 0x010
FACE, HIGHLIGHT, SHADOW = 2, 5, 4  # the kanji's own colours
W, H = 96, 32


def tile_px(data: bytes | bytearray, t: int) -> list[list[int]]:
    b = t * 32
    return [[sum((data[b + (p >> 1) * 16 + y * 2 + (p & 1)] >> (7 - x) & 1) << p for p in range(4)) for x in range(8)]
            for y in range(8)]


def px_tile(px: list[list[int]]) -> bytes:
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            for p in range(4):
                if px[y][x] >> p & 1:
                    out[(p >> 1) * 16 + y * 2 + (p & 1)] |= 0x80 >> x
    return bytes(out)


def banner() -> list[list[bool]]:
    """The English as a 96 x 32 ink mask: src/font/festival-banner.png (tools/gfx/make_banner.py)."""
    img = Image.open(REPO / 'src' / 'font' / 'festival-banner.png').convert('1')
    if img.size != (W, H):
        raise SystemExit(f'festival-banner.png is {img.size}, the banner is {W} x {H}')
    return [[img.getpixel((x, y)) == 0 for x in range(W)] for y in range(H)]


def apply(rom: bytearray) -> None:
    for entry, addr in [(TILES_ENTRY, TILES)] + MAPS:
        o = snes_to_rom(entry)
        if int.from_bytes(rom[o:o + 3], 'little') != addr:
            raise SystemExit(f"${entry:06X} doesn't point at ${addr:06X} (the festival banner)")
    chr_data = bytearray(decompress2(rom, snes_to_rom(TILES) + 1)[0])
    ink = banner()
    plain = tile_px(chr_data, PLAIN)
    order = [0x01 + 0x10 * r + c for r in range(4) for c in range(12)]
    for i, t in enumerate(order):
        ox, oy = (i % 12) * 8, (i // 12) * 8
        px = [[plain[y][x] for x in range(8)] for y in range(8)]
        for y in range(8):
            for x in range(8):
                gy, gx = oy + y, ox + x
                if ink[gy][gx]:  # bevelled like the kanji: lit top-left edge, face, shadow below-right
                    lit = not (gx and ink[gy][gx - 1]) or not (gy and ink[gy - 1][gx])
                    px[y][x] = HIGHLIGHT if lit else FACE
                elif (gx and ink[gy][gx - 1]) or (gy and ink[gy - 1][gx]) or (gx and gy and ink[gy - 1][gx - 1]):
                    px[y][x] = SHADOW
        chr_data[t * 32:t * 32 + 32] = px_tile(px)
    blobs = [(TILES_ENTRY, chr_data)]
    for entry, addr in MAPS:
        tmap = bytearray(decompress(rom, snes_to_rom(addr) + 1)[0])
        cells = [(tmap[i] | tmap[i + 1] << 8) for i in range(0, len(tmap), 2)]
        top = next(i for i, e in enumerate(cells) if e & 0x3FF == 0x001)  # the first glyph's top-left: the inside's first cell
        for r in range(4):
            for c in range(16):
                i = top + r * 32 + c
                tile = PLAIN if c < 2 or c >= 14 else order[r * 12 + c - 2]
                cells[i] = cells[i] & ~0xC3FF | tile
        blobs.append((entry, bytearray(b for e in cells for b in e.to_bytes(2, 'little'))))
    at = AT
    for entry, data in blobs:
        blob = bytes([0xA0]) + len(data).to_bytes(2, 'little') + bytes(data)
        put(rom, at, blob)
        o = snes_to_rom(entry)
        rom[o:o + 3] = at.to_bytes(3, 'little')
        at += len(blob)
    print('  festival banner in English')
