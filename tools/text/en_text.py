"""English script layout and encoding, shared by the insert patch (src/patches/20-text.py) and the checker.

A `final` line is plain text plus:
  " / "     a new page (encoded D8 DA: wait for a button, then clear the box)
  {E3 00 00} raw control bytes, kept as written (hex)
Lines are wrapped here at word boundaries by pixel width (DB between lines), so the game's own
14-character wrap never triggers. Letters are the two-byte codes $01xx (xx = ASCII), drawn by the VWF
(src/patches/15-vwf.py).
"""

import json
import re
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FONT_JSON = REPO / 'src' / 'font' / 'en-vwf.json'
LINE_PX = 168  # the 12 px window mode: 14 characters x 12 px = 21 columns of 8 px (42 tiles a line)
LINES_PER_PAGE = 3
NEWLINE, WAIT, PAGE = 0xDB, 0xD8, 0xDA
TOKEN = re.compile(r'\{([0-9A-Fa-f ]+)\}| / |.', re.S)


class TextError(Exception):
    pass


def widths() -> dict[str, int]:
    return json.loads(FONT_JSON.read_text())['widths']


def tokens(text: str) -> list[tuple[str, object]]:
    """('ch', c) / ('page', None) / ('raw', bytes) in order."""
    out = []
    for m in TOKEN.finditer(text):
        if m.group(1) is not None:
            out.append(('raw', bytes.fromhex(m.group(1))))
        elif m.group(0) == ' / ':
            out.append(('page', None))
        else:
            out.append(('ch', m.group(0)))
    return out


def layout(text: str, w: dict[str, int] | None = None, line_px: int = LINE_PX) -> list[list[list[tuple[str, object]]]]:
    """Pages of lines of tokens, wrapped greedily at spaces to `line_px` (LINE_PX). Raw codes have no width."""
    w = w or widths()
    LINE_PX = line_px
    pages, page, line, word = [], [], [], []
    px = 0

    def width(toks):
        return sum(w[t[1]] for t in toks if t[0] == 'ch')

    def flush_word():
        nonlocal line, px, word
        if not word:
            return
        ww = width(word)
        if line and px + ww > LINE_PX:
            while line and line[-1] == ('ch', ' '):
                line.pop()
            page.append(line)
            line, px = [], 0
        if ww > LINE_PX:
            raise TextError(f'word wider than a line: {"".join(str(t[1]) for t in word)!r}')
        line.extend(word)
        px += ww
        word = []

    for t in tokens(text):
        if t[0] == 'ch':
            if t[1] not in w:
                raise TextError(f'no glyph for {t[1]!r}')
            if t[1] == ' ':
                flush_word()
                if line:
                    line.append(t)
                    px += w[' ']
            else:
                word.append(t)
        elif t[0] == 'raw':
            word.append(t)
        else:  # page
            flush_word()
            while line and line[-1] == ('ch', ' '):
                line.pop()
            page.append(line)
            pages.append(page)
            page, line, px = [], [], 0
    flush_word()
    while line and line[-1] == ('ch', ' '):
        line.pop()
    if line or page:
        page.append(line)
        pages.append(page)
    return pages


def line_px(line, w: dict[str, int] | None = None) -> int:
    w = w or widths()
    return sum(w[t[1]] for t in line if t[0] == 'ch')


PUNCT = str.maketrans({'\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u2013': '-',
                       '\u2014': '-', '\u00a0': ' ', '\u3000': ' ', '\u300c': '"', '\u300d': '"', '\u300e': '"', '\u300f': '"', '\u2606': '', '\u2605': '', '\\': ''})


def normalize(text: str) -> str:
    """A machine draft with typographic punctuation and accents reduced to the font's plain ASCII."""
    text = unicodedata.normalize('NFKD', text.translate(PUNCT))
    return ''.join(c for c in text if not unicodedata.combining(c))


def encode(text: str) -> bytes:
    """The script bytes for `text` (no terminator). No line breaks are written: the VWF breaks a line at a space when
    the next word won't fit the window (src/patches/15-vwf.py `vwf_wrap`, which hands the game its own DB, so a full
    page is the game's business too). Only ` / ` (a new page) and raw codes become control bytes."""
    w = widths()
    out = bytearray()
    space = False  # a space is pending: written only between two letters
    for kind, v in tokens(text):
        if kind == 'ch':
            if v not in w:
                raise TextError(f'no glyph for {v!r}')
            if v == ' ':
                space = bool(out) and out[-1:] != bytes([PAGE])
                continue
            if space:
                out += bytes([0x01, 0x20])
                space = False
            out += bytes([0x01, ord(v)])
        elif kind == 'raw':
            out += v
        else:
            out += bytes([WAIT, PAGE])
            space = False
    return bytes(out)


def parse_addr(s: str) -> int:
    """'C7:1BC2' -> 0xC71BC2."""
    bank, off = s.split(':')
    return int(bank, 16) << 16 | int(off, 16)
