#!/usr/bin/env python3
"""Dump the game's script text runs to JSON, keyed by each run's first address.

    python3 -I tools/text/dump_script.py [--charmap FILE] [--out build/script-dump.json]

Walks the script from the game's entry points (script_vm.py) and writes one entry per run of characters, plus the
$FC-terminated strings of the name/item/menu tables (with a `table` field):

    {"C5:3B80": {"text": "<0x99><0x12>{D1}...", "codes": "0099 0012 D1 ...", "end": "C5:3BC9"}}

Characters are font codes (`<0xNN>`) unless `--charmap` gives a JSON map of code (hex) -> {"ch": character}.
Line breaks D0-D2 appear as `{Dn}`; any other control code ends a run.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rom'))
from script_vm import all_string_tables, jump_targets, read_string, walk_entry_points  # noqa: E402
from RomExtract import REPO  # noqa: E402

INLINE = {0xD0, 0xD1, 0xD2}


def hexcode(code: int) -> str:
    return f'{code:02X}' if code < 0x100 else f'{code:04X}'


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--charmap', type=Path, help='JSON map of font code (hex) -> {"ch": character}')
    ap.add_argument('--out', type=Path, default=REPO / 'build' / 'script-dump.json')
    args = ap.parse_args()
    charmap = json.loads(args.charmap.read_text()) if args.charmap else {}

    def char(code: int) -> str:
        entry = charmap.get(hexcode(code))
        return entry['ch'] if entry else f'<0x{code:X}>'

    def text(codes) -> str:
        return ''.join(f'{{D{c - 0xD0:X}}}' if c in INLINE else char(c) for c in codes)

    good, tokens = walk_entry_points()
    targets = jump_targets(tokens)  # a jump into a run's middle starts a run there
    runs: dict[str, dict] = {}
    run, prev_end = None, None
    for (bank, off), (code, _args, nxt) in sorted(tokens.items()):
        if code < 0xD0 or code >= 0x400 or code in INLINE:
            if run is None or prev_end != (bank, off) or (bank, off) in targets:
                run = {'codes': []}
                runs[f'{bank:02X}:{off:04X}'] = run
            run['codes'].append(code)
            run['end'] = f'{bank:02X}:{nxt:04X}'
            prev_end = (bank, nxt)
        else:
            run = None
    out = {k: {'text': text(r['codes']), 'codes': ' '.join(map(hexcode, r['codes'])), 'end': r['end']}
           for k, r in runs.items()}
    tables = 0
    for bank, table, offsets in all_string_tables():
        tables += 1
        for i, off in enumerate(offsets):
            key = f'{bank:02X}:{off:04X}'
            if key not in out:
                codes, end = read_string(bank, off)
                out[key] = {'text': text(codes), 'codes': ' '.join(map(hexcode, codes)),
                            'end': f'{bank:02X}:{end:04X}', 'table': f'{bank:02X}:{table:04X}[{i}]'}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f'{len(good)} entry points, {tables} string tables -> {len(out)} runs -> {args.out}')


if __name__ == '__main__':
    main()
