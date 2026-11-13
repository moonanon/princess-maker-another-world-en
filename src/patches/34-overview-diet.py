"""The status overview's diet setting (profile, by the fork icon) in English: Balanced / Hearty / Light / Diet.

The overview's BG2 characters are asset CE0242 (format 2, table entry C9 `$0372`, decoded by tools/gfx/lz.py
decompress2, verified byte for byte against VRAM `$6000`). The four words are 64x16 px, ink colour 15: setting k
($7E:95AC & 3) uses top tiles `$30`, `$38`, `$50`, `$58` (+0..7) and the bottom ones `$10` higher (seen with the setting
poked). They are redrawn from the English font and the asset stored raw (format 0)."""

import importlib.util
import sys
from pathlib import Path

from _layout import GFX2, REPO, put, snes_to_rom

sys.path.insert(0, str(REPO / 'tools' / 'gfx'))
from lz import decompress2  # noqa: E402

ENTRY, ASSET = 0xC90372, 0xCE0242
AT = GFX2 + 0x1100  # after 32-halfwidth-font.py's raw font (0x1003 bytes)
WORDS = [(0x30, 'Balanced'), (0x38, 'Hearty'), (0x50, 'Light'), (0x58, 'Diet')]
INK = 15


def apply(rom: bytearray) -> None:
    o = snes_to_rom(ENTRY)
    if int.from_bytes(rom[o:o + 3], 'little') != ASSET:
        raise SystemExit(f"${ENTRY:06X} doesn't point at ${ASSET:06X}")
    chr_data = bytearray(decompress2(rom, snes_to_rom(ASSET) + 1)[0])
    spec = importlib.util.spec_from_file_location('ov', Path(__file__).with_name('30-overview-labels.py'))
    ov = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ov)
    glyphs, widths = ov.font()
    for top, word in WORDS:
        img = [[0] * 64 for _ in range(16)]
        x = 1
        for ch in word:
            for y in range(16):
                for gx in range(8):
                    if glyphs[ch][y] & 0x80 >> gx and x + gx < 64:
                        img[y][x + gx] = INK
            x += widths[ch]
        if x > 64:
            raise SystemExit(f'{word}: {x} px, the space is 64')
        for half in (0, 1):
            for c in range(8):
                t = top + half * 0x10 + c
                px = [[img[half * 8 + y][c * 8 + xx] for xx in range(8)] for y in range(8)]
                chr_data[t * 32:t * 32 + 32] = ov.px_tile(px)
    blob = bytes([0xA0]) + len(chr_data).to_bytes(2, 'little') + bytes(chr_data)
    put(rom, AT, blob)
    rom[o:o + 3] = AT.to_bytes(3, 'little')
    print(f'  overview diet word: {" / ".join(w for _, w in WORDS)}')
