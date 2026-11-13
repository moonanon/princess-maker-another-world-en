#!/usr/bin/env python3
"""List runs of one fill byte (FF or 00) in the base ROM, longest first: candidates for free space.

    python3 -I tools/rom/free_space.py [--min 1024]

A run is only a candidate: confirm with an emulator trace that nothing reads or executes it
before a patch puts anything there.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from RomExtract import rom, rom_to_snes  # noqa: E402


def runs(data: bytes, minimum: int) -> list[tuple[int, int, int]]:
    """(file offset, length, fill byte) for every run of FF or 00 of at least `minimum` bytes."""
    out = []
    i = 0
    while i < len(data):
        b = data[i]
        j = i
        while j < len(data) and data[j] == b:
            j += 1
        if b in (0x00, 0xFF) and j - i >= minimum:
            out.append((i, j - i, b))
        i = j
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--min', type=int, default=1024)
    args = ap.parse_args()
    found = runs(rom(), args.min)
    for off, n, b in sorted(found, key=lambda r: -r[1]):
        print(f'{rom_to_snes(off):06X}-{rom_to_snes(off + n - 1):06X}  {n:6d} bytes of {b:02X}')
    print(f'{len(found)} runs, {sum(n for _, n, _ in found)} bytes')


if __name__ == '__main__':
    main()
