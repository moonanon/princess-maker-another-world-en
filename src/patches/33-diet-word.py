"""The diet setting in the main screen's status box and the profile in English: Balanced / Hearty / Light / Diet.

The four words are pre-drawn 2bpp tiles at C7 `$0132`: 10 tiles (80x8 px, ink colour 1) per setting, in the order of
the string table C7 `$09FD` (Normal, Sturdy, Graceful, Diet), uploaded to VRAM `$2138` when the box is drawn.
Redrawn here with the 5x7 font of 19-status-name.py,
centred, 6 px a letter."""

import importlib.util
from pathlib import Path

from _layout import snes_to_rom

AT = 0xC70132
WORDS = ['Balanced', 'Hearty', 'Light', 'Diet']
WIDTH = 80


def apply(rom: bytearray) -> None:
    spec = importlib.util.spec_from_file_location('sn', Path(__file__).with_name('19-status-name.py'))
    sn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sn)
    o = snes_to_rom(AT)
    if not any(rom[o:o + 160]) or any(rom[o + 2 * y + 1] for t in range(40) for y in range(8) if False):
        raise SystemExit(f'${AT:06X}: diet words not found')
    for i, word in enumerate(WORDS):
        px = [[0] * WIDTH for _ in range(8)]
        x = (WIDTH - (6 * len(word) - 1)) // 2
        for ch in word:
            for y, row in enumerate(sn.FONT[ch].split('|')):
                for dx, c in enumerate(row):
                    if c == '#':
                        px[y][x + dx] = 1
            x += 6
        for t in range(10):
            b = o + (i * 10 + t) * 16
            tile = bytearray(16)
            for y in range(8):
                tile[2 * y] = sum(0x80 >> xx for xx in range(8) if px[y][t * 8 + xx])
            rom[b:b + 16] = tile
    print(f'  diet words: {" / ".join(WORDS)}')
