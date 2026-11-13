#!/usr/bin/env python3
"""The game's LZ formats (asset formats 4, decompressor $80:A493, and 3, $80:A405).

    python3 -I tools/gfx/lz.py C9:3CAF out.bin      # decompress the asset at that address (header byte included)

An asset starts with a format byte (low nibble 4 = LZ), then a 16-bit output size, then the stream. Flag bits are read
low bit first from a flag byte, refilled every 8 bits: 1 = copy one literal byte; 0 1 = long match: two bytes b0 b1,
offset = (b1 >> 3) << 8 | b0 (back from the output position), length = (b1 & 7) + 2, or a third byte + 1 when b1 & 7 is
0; 0 0 = short match: two more flag bits n (first bit high), length n + 3, offset = one byte.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rom'))


def decompress(data: bytes, at: int) -> tuple[bytes, int]:
    """(output, bytes consumed) for the LZ stream whose 16-bit size word is at data[at]."""
    size = data[at] | data[at + 1] << 8
    p = at + 2
    out = bytearray()
    flags, left = 0, 0

    def bit() -> int:
        nonlocal flags, left, p
        if left == 0:
            flags, left = data[p], 8
            p += 1
        b = flags & 1
        flags >>= 1
        left -= 1
        return b

    while len(out) < size:
        if bit():
            out.append(data[p])
            p += 1
            continue
        if bit():
            b0, b1 = data[p], data[p + 1]
            p += 2
            offset = (b1 >> 3) << 8 | b0
            if b1 & 7:
                length = (b1 & 7) + 2
            else:
                length = data[p] + 1
                p += 1
        else:
            n = bit() << 1
            n |= bit()
            length = n + 3
            offset = data[p]
            p += 1
        start = len(out) - offset
        for i in range(length):
            if len(out) >= size:
                break
            out.append(out[start + i])
    return bytes(out), p - at


def decompress3(data: bytes, at: int) -> tuple[bytes, int]:
    """Format 3 ($80:A405): flag 1 = literal; 0 = match b0 b1, offset = (b1 >> 4) << 8 | b0, length = (b1 & 15) + 3."""
    size = data[at] | data[at + 1] << 8
    p = at + 2
    out = bytearray()
    flags, left = 0, 0
    while len(out) < size:
        if left == 0:
            flags, left = data[p], 8
            p += 1
        b = flags & 1
        flags >>= 1
        left -= 1
        if b:
            out.append(data[p])
            p += 1
            continue
        b0, b1 = data[p], data[p + 1]
        p += 2
        start = len(out) - ((b1 >> 4) << 8 | b0)
        for i in range((b1 & 15) + 3):
            if len(out) >= size:
                break
            out.append(out[start + i])
    return bytes(out), p - at


def main() -> None:
    from RomExtract import rom, snes_to_rom
    data = rom()
    bank, off = sys.argv[1].split(':')
    at = snes_to_rom(int(bank, 16) << 16 | int(off, 16))
    fmt = data[at]
    if fmt & 0x0F not in (3, 4):
        raise SystemExit(f'format byte {fmt:02X}: not LZ (3 or 4)')
    out, used = (decompress if fmt & 0x0F == 4 else decompress3)(data, at + 1)
    Path(sys.argv[2]).write_bytes(out)
    print(f'{sys.argv[1]}: format {fmt:02X}, {used + 1} bytes -> {len(out)}')


if __name__ == '__main__':
    main()


def decompress2(data: bytes, at: int) -> tuple[bytes, int]:
    """Format 2 (`80:9CF1`), `at` just past the format byte: word output size, a byte (bit 7: 8 bytes of a 16-nibble
    pixel remap follow; low 7 bits n = bytes per flag bit), then per 32-byte tile 32/(8n) flag bytes, each bit (low
    first) n literal bytes or n zeros; the remap (`80:9DBD`) maps every pixel's 4-bit value through the table; the
    tile is written interleaved (out[2i] = buf[i], out[2i+1] = buf[i+16]). Returns (data, offset past the input)."""
    size = int.from_bytes(data[at:at + 2], 'little')
    mode = data[at + 2]
    n = mode & 0x7F
    p = at + 3
    table = None
    if mode & 0x80:
        table = []
        for b in data[p:p + 8]:
            table += [b >> 4, b & 0x0F]
        p += 8
    groups = {1: 4, 2: 2, 4: 1}[n]
    out = bytearray()
    while len(out) < size:
        buf = bytearray()
        for _ in range(groups):
            flags = data[p]
            p += 1
            for bit in range(8):
                if flags >> bit & 1:
                    buf += data[p:p + n]
                    p += n
                else:
                    buf += bytes(n)
        if table is not None:
            for r in range(8):
                a, b, c, d = buf[r], buf[8 + r], buf[16 + r], buf[24 + r]  # $0C, $14, $1C, $24
                na = nb = nc = nd = 0
                for x in range(8):
                    m = 0x80 >> x
                    v = (bool(d & m) << 3) | (bool(b & m) << 2) | (bool(c & m) << 1) | bool(a & m)
                    v = table[v]
                    na |= m if v & 1 else 0
                    nc |= m if v & 2 else 0
                    nb |= m if v & 4 else 0
                    nd |= m if v & 8 else 0
                buf[r], buf[8 + r], buf[16 + r], buf[24 + r] = na, nb, nc, nd
        for i in range(16):
            out += bytes([buf[i], buf[i + 16]])
    return bytes(out[:size]), p
