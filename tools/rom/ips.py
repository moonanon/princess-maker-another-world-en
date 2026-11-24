#!/usr/bin/env python3
"""IPS create/apply (no external deps).

    python3 -I tools/rom/ips.py make <base.sfc> <patched.sfc> <out.ips>
    python3 -I tools/rom/ips.py apply [<base.sfc> [<patch.ips> [<out.sfc>]]]

`apply` defaults: roms/base.sfc, build/princess-maker-en.ips, dist/eng-out-<YYYYmmdd-HHMMSS>.sfc (the .sfc is
gitignored).
"""

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

MAX_OFFSET = 0xFFFFFF
EOF_MARK = 0x454F46  # "EOF" as an offset would be read as the end marker, so records never start there


def make(base: bytes, new: bytes) -> bytes:
    if len(new) < len(base):
        raise SystemExit('IPS cannot shrink a ROM')
    # `apply` zero-fills past the end of the base, so an expansion's zero padding needs no records, only its length.
    padded = len(new) - len(base)
    if padded > 0:
        base = base + bytes(padded)
    out = bytearray(b'PATCH')
    i, n, reach = 0, len(new), 0
    while i < n:
        if i < len(base) and base[i] == new[i]:
            i += 1
            continue
        start = i
        # Extend through short matching gaps (<= 6 bytes) so records stay few; cap at 0xFFFF per record.
        end = i
        while end < n and end - start < 0xFFFF:
            if end >= len(base) or base[end] != new[end]:
                end += 1
                continue
            gap = end
            while gap < n and gap < len(base) and base[gap] == new[gap] and gap - end <= 6:
                gap += 1
            if gap - end > 6 or gap >= n:
                break
            end = gap
        if start == EOF_MARK:  # back up one byte so the offset isn't the EOF marker
            start -= 1
        end = min(end, start + 0xFFFF)
        chunk = new[start:end]
        out += start.to_bytes(3, 'big') + len(chunk).to_bytes(2, 'big') + chunk
        i = reach = end
    if padded > 0 and reach < n:  # the last bytes are zero padding: one record keeps the patched ROM's length
        out += (n - 1).to_bytes(3, 'big') + b'\x00\x01\x00'
    out += b'EOF'
    return bytes(out)


def apply(base: bytes, patch: bytes) -> bytes:
    if patch[:5] != b'PATCH':
        raise SystemExit('not an IPS file')
    rom = bytearray(base)
    p = 5
    while patch[p : p + 3] != b'EOF':
        off = int.from_bytes(patch[p : p + 3], 'big')
        size = int.from_bytes(patch[p + 3 : p + 5], 'big')
        p += 5
        if size == 0:  # RLE record
            run = int.from_bytes(patch[p : p + 2], 'big')
            data = patch[p + 2 : p + 3] * run
            p += 3
        else:
            data = patch[p : p + size]
            p += size
        if off + len(data) > len(rom):
            rom.extend(b'\0' * (off + len(data) - len(rom)))
        rom[off : off + len(data)] = data
    return bytes(rom)


def main() -> None:
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ('', [])
    if cmd == 'make' and len(args) == 3:
        a, b, out = (Path(x) for x in args)
        out.write_bytes(make(a.read_bytes(), b.read_bytes()))
    elif cmd == 'apply' and len(args) <= 3:
        defaults = [REPO / 'roms' / 'base.sfc', REPO / 'build' / 'princess-maker-en.ips',
                    REPO / 'dist' / f'eng-out-{time.strftime("%Y%m%d-%H%M%S")}.sfc']
        base, patch, out = (Path(x) for x in args + [str(d) for d in defaults[len(args):]])
        out.write_bytes(apply(base.read_bytes(), patch.read_bytes()))
        print(out)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
