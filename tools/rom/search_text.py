#!/usr/bin/env python3
"""Find Japanese text in the base ROM, to learn how the game encodes it.

    python3 -I tools/rom/search_text.py <text> [--relative] [--max N]

Without --relative it looks for the text as Shift-JIS and as half-width katakana (JIS X 0201, as the
internal header is written). With --relative it does a relative search: the game's own table is
unknown, so it looks for byte runs (8-bit, and 16-bit little- and big-endian) whose differences match
the kana's differences in the usual gojuon order (Unicode's hiragana/katakana order, small kana
interleaved). Use 4+ kana from one script (all hiragana or all katakana) with no kanji,
punctuation or voiced kana (games often keep voiced ga/pa apart from ka/ha); a hit's base value is the code
of the first kana.
"""

import argparse
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from RomExtract import rom as load_rom, rom_to_snes  # noqa: E402


def kana_index(ch: str) -> int:
    """A kana's place in Unicode's order, hiragana and katakana alike."""
    code = ord(ch)
    if 0x30A1 <= code <= 0x30F6:
        code -= 0x60
    if not 0x3041 <= code <= 0x3096:
        raise SystemExit(f'{ch!r} ({unicodedata.name(ch, "?")}) is not kana; relative search needs kana only')
    return code - 0x3041


def literal(data: bytes, text: str, limit: int) -> None:
    for name, enc in (('shift-jis', 'shift_jis'), ('half-width', 'jis_x_0201')):
        try:
            needle = unicodedata.normalize('NFKC', text).encode(enc) if enc == 'shift_jis' else to_halfwidth(text).encode('shift_jis')
        except (UnicodeEncodeError, ValueError):
            print(f'{name}: not encodable')
            continue
        hits, at = [], data.find(needle)
        while at != -1 and len(hits) < limit:
            hits.append(at)
            at = data.find(needle, at + 1)
        print(f'{name} ({needle.hex(" ")}): ' + (', '.join(f'{h:06X} (${rom_to_snes(h):06X})' for h in hits) or 'none'))


VOICING = {'\u3099': '\uff9e', '\u309a': '\uff9f'}


def to_halfwidth(text: str) -> str:
    """Full-width kana -> half-width katakana (NFKC goes the other way, so map by name)."""
    out = []
    for ch in unicodedata.normalize('NFD', text):
        if ch in VOICING:
            out.append(VOICING[ch])
            continue
        if 0x3041 <= ord(ch) <= 0x3096:
            ch = chr(ord(ch) + 0x60)
        name = unicodedata.name(ch, '')
        try:
            out.append(unicodedata.lookup('HALFWIDTH ' + name) if name.startswith('KATAKANA') else ch)
        except KeyError:
            out.append(ch)
    return ''.join(out)


def relative(data: bytes, text: str, limit: int) -> None:
    idx = [kana_index(c) for c in text]
    deltas = [b - a for a, b in zip(idx, idx[1:])]
    n = len(idx)
    for width, order in ((1, 'little'), (2, 'little'), (2, 'big')):
        hits = []
        for at in range(len(data) - n * width):
            vals = [int.from_bytes(data[at + i * width : at + (i + 1) * width], order) for i in range(n)]
            if all(b - a == d for a, b, d in zip(vals, vals[1:], deltas)):
                hits.append((at, vals[0] - idx[0]))
                if len(hits) >= limit:
                    break
        label = f'{width * 8}-bit' + (f' {order}' if width > 1 else '')
        print(f'{label}: ' + (', '.join(f'{h:06X} (${rom_to_snes(h):06X}) base={b:X}' for h, b in hits) or 'none'))


def main() -> None:
    ap = argparse.ArgumentParser(description='Find Japanese text in the base ROM.')
    ap.add_argument('text')
    ap.add_argument('--relative', action='store_true')
    ap.add_argument('--max', type=int, default=20)
    args = ap.parse_args()
    (relative if args.relative else literal)(load_rom(), args.text, args.max)


if __name__ == '__main__':
    main()
