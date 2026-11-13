"""How the game lays out a run of English in its window: the VWF's word wrap (src/patches/15-vwf.py) in Python, and a
static map from each run to the window it draws in, so the build can tell which lines won't fit.

The model follows the ROM code, step by step:
- A letter ($01xx) continues the VWF's pen when the last thing drawn in the window was a VWF letter; otherwise the pen
  starts at col_px(column) rounded up to 8 px (`vl_fresh`), plus MARGIN at column 0 of a 12 px window. After it,
  column = ceil(px / 12) (or / 8 in a 16 px window). If the column is already past the limit, the game's new line runs
  first (`eh_draw`): the word breaks in the middle.
- A space ($0120) is a new line instead when pen + space + the next word (letters up to the next space or other code;
  a name printed from RAM, DE 7E:xxxx, counts as its letters) is wider than limit px (`vwf_wrap`).
- A Japanese character (a code < $D0, or $04xx-$07xx): a new line first when the column has reached the limit, then
  column + 1 (+ 2 in a 16 px window, whose columns are 8 px).
- DB a new line; D8 DA a new page.
Window: descriptor word 0 flags (bit $40: 12 px characters), word 6 characters a line (8 px columns in a 16 px
window), word 7 tile rows (a line is 2 tile rows).
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from en_text import widths  # noqa: E402

MARGIN = 2  # 15-vwf.py MARGIN
NAME = 'Melody'  # a name printed from RAM (DE 7E:xxxx) is measured as the default name
TRACED = Path(__file__).resolve().parent / 'window_runs.json'
NEWLINE, WAIT, PAGE, FULL_SPACE = 0xDB, 0xD8, 0xDA, 0x08
DESCRIPTOR = 0xDC  # DC <window> <24-bit descriptor>: copied by $87:8EA0, the column state reset
SELECT = 0xE4  # E4 <window>
# Codes that pass over no text and keep the pen where it is, between a line start and a run
NO_TEXT = {0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xE0, 0xE1, 0xE3, 0xE7, 0xE8, 0xE9, 0xEA, 0xDF}
LINE_START = {NEWLINE, PAGE, DESCRIPTOR}


@dataclass
class Window:
    flags: int
    chars: int
    rows: int
    x: int = 0

    @property
    def px12(self) -> bool:
        return bool(self.flags & 0x40)

    @property
    def limit_px(self) -> int:
        return self.chars * (12 if self.px12 else 8)

    @property
    def lines(self) -> int:
        return max(1, self.rows // 2)


def read_window(rom: bytes, desc: int, snes_to_rom) -> Window:
    o = snes_to_rom(desc)
    word = lambda k: int.from_bytes(rom[o + 2 * k:o + 2 * k + 2], 'little')  # noqa: E731
    return Window(word(0), word(6), word(7), word(4))


@dataclass
class Result:
    pages: list[list[int]] = field(default_factory=list)  # px of each line, per page
    broken_words: list[str] = field(default_factory=list)  # words the game cut in the middle
    wraps: int = 0  # new lines the wrap made (not DB / DA in the text)
    text: list[list[str]] = field(default_factory=list)  # the letters of each line, per page
    breaks: list[list[bool]] = field(default_factory=list)  # per page, each new line: True when the wrap made it

    @property
    def widows(self) -> list[str]:
        """A page's last line holding one word, under a full line: the word left hanging ("...know what I can tell
        you? / example.")."""
        out = []
        for page, px, br in zip(self.text, self.pages, self.breaks):
            if len(page) >= 2 and br and br[-1] and page[-1].strip() and ' ' not in page[-1].strip() and px[-2] > 0:
                out.append(page[-1].strip())
        return out

    @property
    def max_lines(self) -> int:
        return max((len(p) for p in self.pages), default=0)


def simulate(body: bytes, win: Window, w: dict[str, int] | None = None) -> Result:
    """Lay out `body` (script bytes) from a fresh line of `win`, as the VWF and the game do."""
    w = w or widths()
    body = re.sub(rb'\xDE..\x7E', lambda m: b''.join(bytes([1, ord(c)]) for c in NAME), body, flags=re.S)
    step = 12 if win.px12 else 8
    res = Result(pages=[[0]], text=[['']], breaks=[[]])
    col, px, cont = 0, 0, False

    def new_line(wrapped: bool) -> None:
        nonlocal col, px, cont
        res.pages[-1].append(0)
        res.text[-1].append('')
        res.breaks[-1].append(wrapped)
        col, px, cont = 0, 0, False
        res.wraps += wrapped

    def pen() -> int:
        if cont:
            return px
        p = -(-col * step // 8) * 8
        return p if p or not win.px12 else MARGIN

    def letter_px(c: int) -> int:
        return c if c < 0x20 else w.get(chr(c), w[' '])  # $0101-$011F: a blank c px wide

    def word_at(i: int) -> tuple[int, str]:
        total, s = 0, ''
        while i + 1 < len(body) and body[i] == 0x01 and body[i + 1] > 0x20:  # vwf_wrap's word ends at a blank too
            total += letter_px(body[i + 1])
            s += chr(body[i + 1])
            i += 2
        return total, s

    i, in_word = 0, ''
    while i < len(body):
        b = body[i]
        if b == 0x01 and i + 1 < len(body):
            c = body[i + 1]
            i += 2
            if c == 0x20:
                ww, word = word_at(i)
                if pen() + w[' '] + ww > win.limit_px:
                    new_line(True)
                    in_word = word
                    continue
            elif col > win.chars:
                new_line(True)
                res.broken_words.append(in_word or '?')
            in_word = '' if c == 0x20 else in_word
            px = pen() + letter_px(c)
            res.text[-1][-1] += chr(c) if c >= 0x20 else ''
            cont = True
            col = -(-px // step)
            res.pages[-1][-1] = px
            continue
        if b < 0x08 and b >= 0x04 or b < 0xD0:  # a Japanese character (two bytes from $04xx)
            i += 2 if 0x04 <= b < 0x08 else 1
            if col >= win.chars:
                new_line(True)
            col += 1 if win.px12 else 2
            cont = False
            res.pages[-1][-1] = col * step
            continue
        i += 1
        if b == NEWLINE:
            new_line(False)
        elif b == PAGE:
            res.pages.append([0])
            res.text.append([''])
            res.breaks.append([])
            col, px, cont = 0, 0, False
        elif b == 0xDD:
            i += 3  # a native: inline arguments not modelled (the build's own runs carry only clear_wait, none)
        elif b in (0xD3,):
            i += 7
        elif b in (0xD5, 0xD6, 0xDC, 0xE7, 0xE8, 0xE9, 0xEA, 0xE5, 0xE6):
            i += 4 + (b in (0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA))
        elif b in (0xD7, 0xE0, 0xE3):
            i += 2
        elif b in (0xD4, 0xE4):
            i += 1
        elif b in (0xDE, 0xDF, 0xE2, 0xEB, 0xEC, 0xEE):
            i += 3
            cont = cont if b != 0xDE else False  # a call prints something (a name): the pen is no longer known
    return res


def window_map(tokens: dict, rom: bytes, snes_to_rom):
    """run start -> (Window, starts a line) or None for runs where every path back through the walked script (`tokens` from
    script_vm.walk_entry_points) reaches the same `DC` load of the selected window. `starts a line`: every path
    reaches a DB / DA / DC with no text in between. Runs with a window set by game code, or more than one, are left
    out, unless the game was seen drawing them (tools/text/window_runs.json)."""
    prev: dict = {}
    for (b, o), (c, a, n) in tokens.items():
        prev.setdefault((b, n), []).append((b, o))
    cache: dict = {}

    def lookup(start):
        descs, fresh_all, open_end = set(), True, False
        seen, todo = set(), [(start, None, True, 0)]
        while todo:
            cur, sel, fresh, d = todo.pop()
            ps = prev.get(cur)
            if not ps:
                open_end = True
                continue
            for p in ps:
                if (p, sel, fresh) in seen or d > 600:
                    continue
                seen.add((p, sel, fresh))
                c, a, _ = tokens[p]
                s, f = sel, fresh
                if f and c in LINE_START:
                    f = None  # line start found on this path (None: settled)
                elif f and c not in NO_TEXT and c != SELECT:
                    fresh_all = False
                    f = None
                if c == SELECT and s is None:
                    s = a[0]
                if c == DESCRIPTOR and (s is None or a[0] == s):
                    descs.add(int.from_bytes(a[1:4], 'little'))
                    continue
                todo.append((p, s, f, d + 1))
        return descs, fresh_all, open_end

    traced = json.loads(TRACED.read_text()) if TRACED.exists() else {}

    def get(start):
        if start not in cache:
            descs, fresh, open_end = lookup(start)
            cache[start] = ((read_window(rom, next(iter(descs)), snes_to_rom), fresh)
                            if len(descs) == 1 and not open_end else None)
            seen = traced.get(f'{start[0]:02X}:{start[1]:04X}')
            if cache[start] is None and seen:
                cache[start] = (Window(seen['flags'], seen['chars'], seen['rows'], seen['x']), seen['fresh'])
        return cache[start]

    return get


CURSOR_GAP = 2  # px between the menu cursor's tile and an item's first letter
MENU = (0xE5, 0xE6)  # E5/E6 <items> <cursor x> <cursor y> <2 bytes>
MENU_STOP = {0xD8, 0xDA, 0xDE, 0xDF, 0xE4, 0xFC} | set(range(0xF0, 0xFA))


def menu_code(tokens: dict, start: tuple[int, int], limit: int = 80) -> int | None:
    """The address of the E5/E6 menu code that follows the run at `start` in a straight line (its items are drawn
    before it), or None: a wait, page, call, jump or window switch comes first."""
    at = start
    for _ in range(limit):
        tok = tokens.get(at)
        if not tok:
            return None
        code, _, nxt = tok
        if code in MENU:
            return at[0] << 16 | at[1]
        if code in MENU_STOP:
            return None
        at = (at[0], nxt)
    return None


def indent_px(cursor_x: int, window_x: int) -> int:
    """The pen offset (past MARGIN) that puts a menu item's first letter CURSOR_GAP px past the cursor's tile."""
    return max(0, (cursor_x + 1 - window_x) * 8 + CURSOR_GAP - MARGIN)


def blank(px: int) -> bytes:
    """VWF blank-advance codes ($0101-$011F) for `px` pixels."""
    out = bytearray()
    while px > 0:
        n = min(px, 0x1F)
        out += bytes([0x01, n])
        px -= n
    return bytes(out)
