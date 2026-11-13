"""Name and data entry in English: lower-case glyphs for the grid, Start to finish a name, the voicing marks
disabled, the date/age pickers' year/month/day/weekday/age labels replaced (the weekday kanji the picker draws is graphics: not yet).

The grid (C7 `$10AE`) is drawn in the Japanese font (its window has 16 px cells), which has A-Z and 0-9 but only
c g m p in lower case. a-z and ' are drawn from the English font into blank glyphs of that font (codes `$0800`-
`$081A`, all-zero in the base ROM); 15-vwf.py's GRID_MAP shows the grid's cells with them.

The grid's input loop (`$88:9AAF`): `$0A88` holds new presses; A on cell `$44`/`$45`
(the voicing marks) voices the previous kana, which would turn a Latin letter into a kana code, so those compares are moved
out of range and the cells act as plain letters. B (`$8000`) deletes; the code after it (`$88:9C28`) is hooked:
Start (`$1000`) with a name of at least one letter ends entry the way the done cell does (`STZ $00`, on to `$88:9C41`).
"""

import json

from PIL import Image

from asm65816 import assemble
from _layout import FONT_FIRST, NAME_ENTRY_CODE, REPO, put, snes_to_rom

JP_FONT = 0xDD0000
LOWER_FIRST = 0x0800  # a-z then ' : blank glyphs in the base ROM
LOWER = 'abcdefghijklmnopqrstuvwxyz\''
# The date/age pickers' label lines (C7 $1150-$11D0, script text; the picker prints its numbers over the spaces).
# Script text can't use the new glyphs (a two-byte code starts $04-$07), so the line is rebuilt from one-byte codes,
# same cells: year, month -> '-' ($8F), day, weekday, age -> space; the bytes saved end in `DF <next byte>` (a jump that goes nowhere).
PICKER_RANGE = (0xC71150, 0xC711D0)
DATE_LINE = bytes.fromhex('08080804b808080' '51e080806ed08055d')  # 3 sp year 2 sp month 2 sp day sp weekday: 12 cells, 16 bytes
DATE_CELLS = bytes.fromhex('0808088f08088f0808080808')
AGE_LINE = bytes.fromhex('08080808080780')  # 5 sp age
AGE_CELLS = bytes.fromhex('080808')
VOICING = [(0x889B25, 0x44), (0x889B2A, 0x45)]  # CPX #$0044 / #$0045 operands
START_HOOK = 0x889C28
START_HOOK_ORIGINAL = bytes.fromhex('AF860A7E')  # LDA $7E0A86

START_CODE = '''
start_hook:                 ; M16; A = new presses ($0A88), B not pressed
        LDA $7E0A88
        BIT #$1000
        BEQ sh_orig
        LDA $1A             ; letters in the name
        BEQ sh_orig
        STZ $00             ; finished, as the done cell does
        JML $889C41
sh_orig:
        LDA $7E0A86
        JML $889C2C
'''


def jp_glyph_offset(code: int) -> int:
    return snes_to_rom(JP_FONT) + (code - 0x338) * 32


def english_glyph(ch: str) -> list[int]:
    """16 rows of the English font's 8 px glyph for `ch`."""
    meta = json.loads((REPO / 'src' / 'font' / 'en-vwf.json').read_text())
    img = Image.open(REPO / 'src' / 'font' / 'en-vwf.png').convert('1')
    cw, chh = meta['cell']
    i = ord(ch) - FONT_FIRST
    x0, y0 = (i % 16) * cw, (i // 16) * chh
    return [sum(0x80 >> x for x in range(cw) if img.getpixel((x0 + x, y0 + y)) == 0) for y in range(chh)]


# The grid's back (delete) and done cells: those kanji glyphs are redrawn as Del / OK. They are left in only one
# untranslated line (C3:0236, the done kanji), so the change shows nowhere else.
GRID_KEYS = [(0x0594, 'Del'), (0x04C9, 'OK')]


def english_width(ch: str) -> int:
    return json.loads((REPO / 'src' / 'font' / 'en-vwf.json').read_text())['widths'][ch]


def apply(rom: bytearray) -> None:
    for n, ch in enumerate(LOWER):
        at = jp_glyph_offset(LOWER_FIRST + n)
        if any(rom[at:at + 32]):
            raise SystemExit(f'glyph ${LOWER_FIRST + n:04X} is not blank')
        rows = [r << 6 for r in english_glyph(ch)]  # 16 px wide, 2 px in from the left (the grid's letters sit there)
        tiles = [[r >> 8 for r in rows[:8]], [r & 0xFF for r in rows[:8]],
                 [r >> 8 for r in rows[8:]], [r & 0xFF for r in rows[8:]]]
        rom[at:at + 32] = bytes(b for t in tiles for b in t)
    lo, hi = (snes_to_rom(a) for a in PICKER_RANGE)
    for old, cells, want in ((DATE_LINE, DATE_CELLS, 2), (AGE_LINE, AGE_CELLS, 1)):
        found = [i for i in range(lo, hi) if rom[i:i + len(old)] == old]
        if len(found) != want:
            raise SystemExit(f'picker line {old.hex()}: found {len(found)}, expected {want}')
        assert len(old) - len(cells) == 4
        for i in found:
            nxt = PICKER_RANGE[0] + (i - lo) + len(old)
            rom[i:i + len(old)] = cells + bytes([0xDF]) + nxt.to_bytes(3, 'little')
    for code, word in GRID_KEYS:  # back, done: the grid's last two cells, two-byte kanji codes in its text
        rows = [0] * 16
        x = max(0, (16 - sum(english_width(c) for c in word)) // 2)
        for ch in word:
            g = english_glyph(ch)
            for y in range(16):
                rows[y] |= (g[y] << 8) >> x
            x += english_width(ch)
        rows = [r & 0xFFFF for r in rows]
        at = jp_glyph_offset(code)
        tiles = [[r >> 8 for r in rows[:8]], [r & 0xFF for r in rows[:8]],
                 [r >> 8 for r in rows[8:]], [r & 0xFF for r in rows[8:]]]
        rom[at:at + 32] = bytes(b for t in tiles for b in t)
    for addr, value in VOICING:
        o = snes_to_rom(addr)
        if rom[o:o + 2] != bytes([value, 0]):
            raise SystemExit(f'${addr:06X}: expected CPX #${value:04X}')
        rom[o:o + 2] = b'\xFF\x00'
    o = snes_to_rom(START_HOOK)
    if rom[o:o + 4] != START_HOOK_ORIGINAL:
        raise SystemExit(f'${START_HOOK:06X} is not LDA $7E0A86')
    code, labels = assemble(NAME_ENTRY_CODE, START_CODE)
    put(rom, NAME_ENTRY_CODE, code)
    rom[o:o + 4] = bytes([0x5C]) + labels['start_hook'].to_bytes(3, 'little')
