#!/usr/bin/env python3
"""Find which compressed asset (C9 `$0000` table) holds some VRAM bytes: decompress every entry and search.

    python3 -I tools/gfx/find_asset.py build/gfx/bday.vram 0x5140 0x1C0     # VRAM word address, byte count
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rom'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from RomExtract import rom, snes_to_rom  # noqa: E402
from lz import decompress, decompress3  # noqa: E402


def assets(r: bytes):
    t = snes_to_rom(0xC90000)
    for i in range(0, 0x600, 3):
        a = int.from_bytes(r[t + i:t + i + 3], 'little')
        if not 0xC00000 <= a < 0xE00000:
            continue
        o = snes_to_rom(a)
        fmt = r[o] & 0x0F
        try:
            if fmt == 4:
                yield i, a, decompress(r, o + 1)[0]
            elif fmt == 3:
                yield i, a, decompress3(r, o + 1)[0]
            elif fmt == 0:
                n = int.from_bytes(r[o + 1:o + 3], 'little')
                yield i, a, r[o + 3:o + 3 + n]
        except Exception:
            pass


def main() -> None:
    v = Path(sys.argv[1]).read_bytes()
    w, n = int(sys.argv[2], 0), int(sys.argv[3], 0)
    want = v[w * 2:w * 2 + n]
    r = bytes(rom())
    for i, a, data in assets(r):
        for chunk in (want, want[:64]):
            k = data.find(chunk)
            if k >= 0:
                print(f'entry C9:{i:04X} -> ${a:06X} offset {k:#x} ({"all" if chunk is want else "first 64 bytes"})')
                break


if __name__ == '__main__':
    main()
