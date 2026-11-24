"""The title screen's logo plaque in English ("Princess Maker" in place of プリンセスメーカー).

The plaque is 24 sprites of 32 x 32 (OAM 1-24, palette 4), 8 across and 3 down at y 64, so 256 x 96 px. Their tiles are
the title's OBJ sheet, CD `$57F1` (pointer at C9 `$0AA7`, LZ format 4, 0x4000 bytes = VRAM `$0000`-`$1FFF`): the
left four columns use tiles `$000`-`$08F`, the right four `$100`-`$18F`, each 32 x 32 sprite 4 x 4 tiles in a 16-tile
row. This module redraws every plaque pixel from src/font/title-logo.png (256 x 96, indexed in the sprites' own
palette 4, index 0 transparent) and stores the sheet raw (format 0) at GFX5 + 0x8000.
"""

from PIL import Image

from _layout import GFX5, REPO, put, snes_to_rom

import sys
sys.path.insert(0, str(REPO / 'tools' / 'gfx'))
from lz import decompress  # noqa: E402

AT = GFX5 + 0x8000  # past 45-festival-banner.py's tiles and maps (GFX5 + 0x1000)
ENTRY, SHEET = 0xC90AA7, 0xD957F1
W, H = 256, 96


def sprite_tile(col: int, row: int) -> int:
    """The first tile of the plaque's sprite at column `col` (0-7), row `row` (0-2)."""
    return (0x100 if col >= 4 else 0) + (col % 4) * 4 + row * 0x40


def put_px(chr_data: bytearray, t: int, px: list[list[int]]) -> None:
    b = t * 32
    chr_data[b:b + 32] = bytes(32)
    for y in range(8):
        for x in range(8):
            for p in range(4):
                if px[y][x] >> p & 1:
                    chr_data[b + (p >> 1) * 16 + y * 2 + (p & 1)] |= 0x80 >> x


def apply(rom: bytearray) -> None:
    o = snes_to_rom(ENTRY)
    if int.from_bytes(rom[o:o + 3], 'little') != SHEET:
        raise SystemExit(f"${ENTRY:06X} doesn't point at ${SHEET:06X} (the title logo)")
    chr_data = bytearray(decompress(rom, snes_to_rom(SHEET) + 1)[0])
    img = Image.open(REPO / 'src' / 'font' / 'title-logo.png')
    if img.mode != 'P' or img.size != (W, H):
        raise SystemExit(f'title-logo.png must be {W} x {H}, indexed (palette 4)')
    for row in range(3):
        for col in range(8):
            first = sprite_tile(col, row)
            for ty in range(4):
                for tx in range(4):
                    ox, oy = col * 32 + tx * 8, row * 32 + ty * 8
                    px = [[img.getpixel((ox + x, oy + y)) for x in range(8)] for y in range(8)]
                    if any(v > 15 for r in px for v in r):
                        raise SystemExit('title-logo.png uses a colour outside palette 4')
                    put_px(chr_data, first + ty * 16 + tx, px)
    put(rom, AT, bytes([0xA0]) + len(chr_data).to_bytes(2, 'little') + bytes(chr_data))
    rom[o:o + 3] = AT.to_bytes(3, 'little')
    print('  title logo in English')
