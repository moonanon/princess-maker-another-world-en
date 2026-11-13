"""The date pickers' weekday (name entry: birthdays) in English: Sun Mon Tue Wed Thu Fri Sat.

The picker draws the weekday as BG3 tiles `$2228 + day*4` (`88:A229`, `88:A29F`); their
graphics are stored raw at C8 `$028C`: 7 days (Sunday first) x 4 tiles (top-left, top-right, bottom-left, bottom-right),
2bpp, 16 bytes a tile, ink in plane 0 (verified: VRAM `$5140` on the birthday picker = those ROM bytes). Each 16x16
glyph is redrawn centred: capitals from the VWF font, lower case 4 px wide (NARROW) so three letters fit."""

import importlib.util
from pathlib import Path

from _layout import snes_to_rom

AT = 0xC8028C
DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
# Lower case 4 px wide (rows 4-12 of the 16, as the English font's): three letters fit the 16 px glyph
NARROW = {
    'u': '....|....|....|#..#|#..#|#..#|#..#|#..#|.###', 'n': '....|....|....|###.|#..#|#..#|#..#|#..#|#..#',
    'o': '....|....|....|.##.|#..#|#..#|#..#|#..#|.##.', 'e': '....|....|....|.##.|#..#|####|#...|#...|.###',
    'd': '...#|...#|...#|.###|#..#|#..#|#..#|#..#|.###', 'h': '#...|#...|#...|###.|#..#|#..#|#..#|#..#|#..#',
    'r': '....|....|....|#.##|##..|#...|#...|#...|#...', 'a': '....|....|....|.##.|...#|.###|#..#|#..#|.###',
    't': '....|.#..|.#..|###.|.#..|.#..|.#..|.#..|..##', 'i': '....|.#..|....|##..|.#..|.#..|.#..|.#..|###.',
}
SUNDAY_TL = bytes.fromhex('0000000000003f002000200020002000')  # Sunday's top-left tile


def apply(rom: bytearray) -> None:
    o = snes_to_rom(AT)
    if bytes(rom[o:o + 16]) != SUNDAY_TL:
        raise SystemExit(f'${AT:06X} is not the weekday glyphs (Sunday)')
    spec = importlib.util.spec_from_file_location('ov', Path(__file__).with_name('30-overview-labels.py'))
    ov = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ov)
    glyphs, widths = ov.font()
    for d, text in enumerate(DAYS):
        cols = []  # (x, rows 0-15 as bit masks of an 8 px column-set), letter by letter, 1 px apart
        for ch in text:
            if ch in NARROW:
                rows = [0] * 16
                for y, r in enumerate(NARROW[ch].split('|')):
                    rows[4 + y] = sum(0x80 >> x for x, c in enumerate(r) if c == '#')
                cols.append((rows, 4))
            else:
                ink = [x for x in range(8) for y in range(16) if glyphs[ch][y] & 0x80 >> x]
                cols.append(([(r << min(ink)) & 0xFF for r in glyphs[ch]], max(ink) - min(ink) + 1))
        total = sum(w for _, w in cols) + len(cols) - 1
        if total > 16:
            raise SystemExit(f'{text}: {total} px, the glyph is 16')
        x = (16 - total + 1) // 2
        px = [[0] * 16 for _ in range(16)]
        for rows, w in cols:
            for y in range(16):
                for gx in range(w):
                    if rows[y] & 0x80 >> gx:
                        px[y][x + gx] = 1
            x += w + 1
        for t, (tx, ty) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
            tile = bytearray(16)
            for y in range(8):
                tile[2 * y] = sum(0x80 >> xx for xx in range(8) if px[ty + y][tx + xx])
            b = o + (d * 4 + t) * 16
            rom[b:b + 16] = tile
    print(f'  weekdays: {"/".join(DAYS)}')
