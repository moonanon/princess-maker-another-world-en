"""The save/load screen's half-width font in Latin letters: slot names, and "No data" for an empty slot.

The save/load slots are BG3 text in a half-width (8x16) kana font: asset `D9:BB95` (LZ4, 4 KiB, table entry
C9 `$0AB6`) loaded to VRAM `$3800` (chr `$2000`, tiles `$300`-`$3FF`, 2bpp, ink colour 1); kana k of the status box's
list (C7 `$03BD`: blank, then the katakana a i u ...) is tiles `$300 + 2k` (top) and `+1` (bottom).
Name bytes are the name grid's kana codes
(15-vwf.py GRID_CODES), so those kana are redrawn as their letters (from the English font), which shows the slot names
in Latin. The empty-slot text "no data" is a tilemap at C8 `$EA2A` (top row) / `$EA62` (bottom), 11 words
each; it is rewritten as "No data" in those redrawn letters. The font is stored raw (format 0) at GFX2."""

import importlib.util
import sys
from pathlib import Path

from _layout import GFX2, REPO, put, snes_to_rom

sys.path.insert(0, str(REPO / 'tools' / 'gfx'))
from lz import decompress  # noqa: E402

ENTRY, ASSET = 0xC90AB6, 0xD9BB95
LIST = 0xC703BD
NO_DATA_TOP, NO_DATA_BOTTOM, CELLS = 0xC8EA2A, 0xC8EA62, 11
NO_DATA = 'No data'


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def apply(rom: bytearray) -> None:
    o = snes_to_rom(ENTRY)
    if int.from_bytes(rom[o:o + 3], 'little') != ASSET:
        raise SystemExit(f"${ENTRY:06X} doesn't point at ${ASSET:06X}")
    font = bytearray(decompress(rom, snes_to_rom(ASSET) + 1)[0])
    if len(font) != 0x1000:
        raise SystemExit('half-width font: unexpected size')
    vwf, ov = load('15-vwf.py'), load('30-overview-labels.py')
    glyphs, widths = ov.font()
    lst = bytes(rom[snes_to_rom(LIST):snes_to_rom(LIST) + 0x5D])
    index = {}
    for code, ch in zip(vwf.GRID_CODES, vwf.GRID_LETTERS):
        if code in lst and lst.index(code) and ch in glyphs:  # index 0 is the blank every empty cell uses
            k = lst.index(code)
            index[ch] = k
            x0 = max(0, (8 - widths[ch]) // 2)
            for half in (0, 1):
                t = (2 * k + half) * 16
                tile = bytearray(16)
                for y in range(8):
                    row = glyphs[ch][half * 8 + y]
                    tile[2 * y] = (row >> x0) & 0xFF
                font[t:t + 16] = tile
    blob = bytes([0xA0]) + len(font).to_bytes(2, 'little') + bytes(font)
    put(rom, GFX2, blob)
    rom[o:o + 3] = GFX2.to_bytes(3, 'little')
    text = NO_DATA.center(CELLS)
    for at, half in ((NO_DATA_TOP, 0), (NO_DATA_BOTTOM, 1)):
        p = snes_to_rom(at)
        if int.from_bytes(rom[p:p + 2], 'little') != 0x238A + half:
            raise SystemExit(f'${at:06X} is not the empty-slot text (its first glyph)')
        words = b''.join((0x2300 + (2 * index[c] + half if c != ' ' else 0)).to_bytes(2, 'little') for c in text)
        rom[p:p + 2 * CELLS] = words
    print(f'  half-width font: {len(index)} letters; empty slot reads "{NO_DATA}"')
