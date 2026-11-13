#!/usr/bin/env python3
"""Render one BG layer (4bpp, 8x8 tiles) from a VRAM/CGRAM dump and print its tilemap:
for finding which tiles a pre-drawn word uses.

    python3 -I tools/gfx/render_bg.py build/gfx/ov1 --chr 0x4000 --map 0x7400 out.png [--grid]

--chr and --map are VRAM word addresses (the PPU's BG chr/tilemap base). The tilemap is 32x32 entries:
vhopppcc cccccccc (v/h flip, priority, palette, tile).
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def tile_pixels(vram: bytes, chr_word: int, tile: int) -> list[list[int]]:
    base = chr_word * 2 + tile * 32
    rows = []
    for y in range(8):
        p0, p1, p2, p3 = vram[base + y * 2], vram[base + y * 2 + 1], vram[base + 16 + y * 2], vram[base + 17 + y * 2]
        rows.append([(p0 >> (7 - x) & 1) | (p1 >> (7 - x) & 1) << 1 | (p2 >> (7 - x) & 1) << 2 | (p3 >> (7 - x) & 1) << 3
                     for x in range(8)])
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('dump')
    ap.add_argument('--chr', type=lambda s: int(s, 0), required=True)
    ap.add_argument('--map', type=lambda s: int(s, 0), required=True)
    ap.add_argument('out')
    ap.add_argument('--grid', action='store_true')
    a = ap.parse_args()
    vram = Path(a.dump + '.vram').read_bytes()
    cg = Path(a.dump + '.cgram').read_bytes()
    pal = [((c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3) for c in
           (cg[i] | cg[i + 1] << 8 for i in range(0, 512, 2))]
    im = Image.new('RGB', (256, 256))
    for ty in range(32):
        row = []
        for tx in range(32):
            e = vram[(a.map + ty * 32 + tx) * 2] | vram[(a.map + ty * 32 + tx) * 2 + 1] << 8
            tile, p, hf, vf = e & 0x3FF, e >> 10 & 7, e >> 14 & 1, e >> 15 & 1
            row.append(f'{tile:03X}')
            px = tile_pixels(vram, a.chr, tile)
            for y in range(8):
                for x in range(8):
                    c = px[7 - y if vf else y][7 - x if hf else x]
                    im.putpixel((tx * 8 + x, ty * 8 + y), pal[p * 16 + c])
        if ty < 28:
            print(f'{ty:2d} ' + ' '.join(row))
    im = im.resize((768, 768), Image.NEAREST)
    if a.grid:
        d = ImageDraw.Draw(im)
        for i in range(0, 768, 24):
            d.line([(i, 0), (i, 767)], fill=(60, 60, 60))
            d.line([(0, i), (767, i)], fill=(60, 60, 60))
    im.save(a.out)


if __name__ == '__main__':
    main()
