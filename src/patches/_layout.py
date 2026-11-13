"""Where the hack puts things: shared by the patch modules (not applied itself).

Bank $DB is all zero in the base ROM and was never read or executed in 1,500 frames of play from each of several
saved games.
$7F:F000-$7F:F1FF (VWF state, then a ring of 8 column buffers at $F100) is zero in every saved game tried and
never written in play.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for sub in ('tools/rom', 'tools/text'):
    if str(REPO / sub) not in sys.path:
        sys.path.insert(0, str(REPO / sub))

from RomExtract import snes_to_rom as _base_snes_to_rom  # noqa: E402

ROM_SIZE = 0x400000  # the built ROM: 4 MiB (00-expand.py), banks $C0-$FF linear


def snes_to_rom(addr: int) -> int:
    """Like RomExtract.snes_to_rom, but banks $E0-$FF are the expansion, not a mirror of $C0-$DF."""
    if (addr >> 16) >= 0xC0:
        return (addr >> 16 & 0x3F) * 0x10000 + (addr & 0xFFFF)
    return _base_snes_to_rom(addr)

CODE = 0xDB0000  # the VWF and the text-reader hook
NATIVE_CLEAR_WAIT = 0xDB0900  # a `DD` native: clears $7E:A00F, the flag the E1 wait code waits on (17-natives.py)
NATIVE_FIT = 0xDB0A00  # a `DD` native + <px> <24-bit fallback>: goes on to the English only if it fits the line (17-natives.py)
NAME_MAP = 0xDB0B00  # 256 bytes: name kana code -> ASCII (15-vwf.py `name_map`); 0 = not remapped
GRID_MAP = 0xDB0C00  # 256 words: grid kana code -> the Japanese font code shown in the grid (to $DB0DFF)
GFX = 0xF80000  # re-drawn graphics assets (30-*.py), raw format 0
GFX2 = 0xF90000  # 32-halfwidth-font.py: the save screen's half-width font, raw format 0
GFX3 = 0xFC0000  # 35-item-cards.py: the item cards (shop, equipment), raw format 0, two banks
GFX4 = 0xFA0000  # 41-board-names.py: the festival results boards' rival names, raw format 0
GFX5 = 0xFB0000  # 44-board-daughter-name.py: the bracket's 8x8 katakana font, raw format 0
WINDOW_SETUP_CODE_AT = 0xDB0EC0  # 15-vwf.py: VWF state reset when a window is set up
LIST_CURSOR_CODE = 0xDB0E80  # 18-windows.py: the shop list cursor's column
NAME_ENTRY_CODE = 0xDB0E00  # 16-name-entry.py: the Start hook
E1_HOOK_CODE = 0xDB0940  # the E1 wait's start, hooked at $87:8FD8
EARLY_HOME_CODE = 0xDB0F80  # src/gamefix/questing/10-reputation.py: going home early grants the days spent
QUESTING_CODE = 0xDB1800  # src/gamefix/questing/20-people.py: code + its message script (after the font, $DB:15F0)
BUGFIX_CODE = 0xDB1E00  # src/gamefix/bugfix/*.py: code and script bits
WIDTHS = 0xDB0800  # one byte per glyph from U+0020: advance in pixels
FONT = 0xDB1000  # 16 bytes per glyph from U+0020: rows 0-15, 1bpp, bit 7 = leftmost pixel
TEXT_FIRST_BANK, TEXT_LAST_BANK = 0xE0, 0xFF  # English script reached by DF detours: the expansion
# Which field of a src/text entry is inserted, first match wins (set by tools/rom/build.py --text).
TEXT_FIELDS = ['final', 'claude', 'templates', 'labels', 'draft']
# Script runs another patch module rewrites (16-name-entry.py's date/age picker labels): 20-text.py leaves them alone
RESERVED_RUNS = {'C7:1173', 'C7:119C', 'C7:11C3'}
TEXT_SKIP: set[str] = set()  # entry keys left Japanese (build.py --skip, to bisect a bad line)
FONT_FIRST, FONT_COUNT = 0x20, 0x5F
# Condensed letters (the overview labels' tiny set, _narrow.py TINY) for stat labels drawn as text: code $01xx with
# xx = the letter's ASCII + CONDENSED, glyph index FONT_COUNT+1.. (WIDTHS runs on; the rows are at CFONT).
CONDENSED = 0x60
CFONT = 0xDB2000  # 16 bytes per condensed glyph, from the condensed space ($0180)
VWF_GLYPHS = 0xC0  # glyph indices the VWF accepts: the font, then the condensed set


def put(rom: bytearray, addr: int, data: bytes) -> None:
    """Write `data` at SNES address `addr`, refusing to cross a bank or to overwrite non-zero bytes."""
    off = snes_to_rom(addr)
    if (addr & 0xFFFF) + len(data) > 0x10000:
        raise SystemExit(f'${addr:06X}+{len(data)} crosses a bank')
    if any(rom[off:off + len(data)]):
        raise SystemExit(f'${addr:06X}+{len(data)} is not free')
    rom[off:off + len(data)] = data


class TextAllocator:
    """Hands out room for English chunks in the expansion banks. A chunk never crosses a bank: the script
    pointer's offset is 16 bits, so the reader would wrap inside the bank."""

    def __init__(self) -> None:
        self.bank, self.off = TEXT_FIRST_BANK, 0

    def alloc(self, size: int) -> int:
        if size > 0x10000:
            raise SystemExit('one English chunk is larger than a bank')
        if self.off + size > 0x10000:
            self.bank, self.off = self.bank + 1, 0
            if self.bank > TEXT_LAST_BANK:
                raise SystemExit('English text area full')
        addr = self.bank << 16 | self.off
        self.off += size
        return addr
