"""The English variable-width font (src/font/en-vwf.png + .json) -> FONT (glyph rows) and WIDTHS (advances)."""

import json

from PIL import Image

from _layout import FONT, FONT_COUNT, FONT_FIRST, REPO, WIDTHS, put


def apply(rom: bytearray) -> None:
    meta = json.loads((REPO / 'src' / 'font' / 'en-vwf.json').read_text())
    img = Image.open(REPO / 'src' / 'font' / 'en-vwf.png').convert('1')
    cw, ch = meta['cell']
    assert (cw, ch) == (8, 16) and meta['first'] == FONT_FIRST
    glyphs, widths = bytearray(), bytearray()
    for i in range(FONT_COUNT):
        c = chr(FONT_FIRST + i)
        x0, y0 = (i % 16) * cw, (i // 16) * ch
        for y in range(ch):
            row = 0
            for x in range(cw):
                if img.getpixel((x0 + x, y0 + y)) == 0:
                    row |= 0x80 >> x
            glyphs.append(row)
        w = meta['widths'].get(c, 0)
        assert 0 <= w <= 8, c
        widths.append(w)
    put(rom, FONT, bytes(glyphs))
    put(rom, WIDTHS, bytes(widths))
