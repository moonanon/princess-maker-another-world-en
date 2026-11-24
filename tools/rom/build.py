#!/usr/bin/env python3
"""Build the translation: base ROM + every src/patches/[0-9]*.py (in name order; _*.py are shared helpers) -> build/princess-maker-en.sfc + build/princess-maker-en.ips.

    python3 -I tools/rom/build.py                          # the English script, src/text/script-en.json
    python3 -I tools/rom/build.py --variant questing       # the English + the game's bug fixes + the questing rework

Variants (each its own IPS against the base ROM): `en` (the translation), `bugfix` (+ src/gamefix/bugfix/*.py, fixes to
the original game's own bugs), `questing` (+ bugfix + src/gamefix/questing/*.py, the quest encounter rework). The game
fixes run after the translation's modules, so they may rely on its expanded ROM and free-space allocator.

Each patch module defines `apply(rom: bytearray) -> None` and edits the ROM in place at file offsets
(use RomExtract.snes_to_rom for SNES addresses). A patch that needs more room may grow the ROM (an
expansion to 3 or 4 MiB is a patch of its own, applied first). The SNES header checksum is fixed after
the patches run, and the IPS is made against the base ROM and round-trip verified before it is written.
"""

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from RomExtract import REPO, rom  # noqa: E402
import ips  # noqa: E402

HEADER = 0xFFC0  # HiROM internal header
OUT_ROM = REPO / 'build' / 'princess-maker-en.sfc'
OUT_IPS = REPO / 'build' / 'princess-maker-en.ips'
VARIANTS = {'en': [], 'bugfix': ['bugfix'], 'questing': ['bugfix', 'questing']}  # extra src/gamefix/ dirs, in order


def variant_paths(variant: str) -> tuple[Path, Path]:
    """The ROM and IPS a variant writes by default: princess-maker-en[-variant].sfc/.ips."""
    suffix = '' if variant == 'en' else f'-{variant}'
    return OUT_ROM.with_name(f'princess-maker-en{suffix}.sfc'), OUT_IPS.with_name(f'princess-maker-en{suffix}.ips')


def fix_checksum(data: bytearray) -> None:
    """Write the header's checksum and its complement for the ROM as it now stands."""
    data[HEADER + 0x1C : HEADER + 0x20] = b'\xff\xff\x00\x00'
    total = sum(data) & 0xFFFF
    data[HEADER + 0x1C : HEADER + 0x1E] = (total ^ 0xFFFF).to_bytes(2, 'little')
    data[HEADER + 0x1E : HEADER + 0x20] = total.to_bytes(2, 'little')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--skip', default='', help='entry keys (C7:1A00,...) left Japanese: bisects a line that breaks the game')
    ap.add_argument('--variant', choices=VARIANTS, default='en', help='which patch: the translation, + bug fixes, + questing rework')
    ap.add_argument('--out', type=Path, help='where to write the patched ROM (the IPS is only written for the default)')
    args = ap.parse_args()
    out_rom, out_ips = variant_paths(args.variant)
    args.out = args.out or out_rom
    base = rom()
    out = bytearray(base)
    sys.path.insert(0, str(REPO / 'src' / 'patches'))
    import _layout  # noqa: E402
    _layout.TEXT_SKIP.update(k for k in args.skip.split(',') if k)
    dirs = [REPO / 'src' / 'patches'] + [REPO / 'src' / 'gamefix' / d for d in VARIANTS[args.variant]]
    for path in [p for d in dirs for p in sorted(d.glob('[0-9]*.py'))]:  # _*.py are shared helpers
        spec = importlib.util.spec_from_file_location(path.stem, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.apply(out)
        print(f'applied {path.name}')
    if bytes(out) != base:
        fix_checksum(out)
    patch = ips.make(base, bytes(out))
    if ips.apply(base, patch) != bytes(out):
        raise SystemExit('IPS round-trip mismatch')
    args.out.parent.mkdir(exist_ok=True)
    args.out.write_bytes(out)
    if args.out == out_rom:
        out_ips.parent.mkdir(exist_ok=True)
        out_ips.write_bytes(patch)
    print(f'{sum(a != b for a, b in zip(base, out)) + sum(1 for b in out[len(base):] if b)} bytes changed; IPS {len(patch)} bytes')


if __name__ == '__main__':
    main()
