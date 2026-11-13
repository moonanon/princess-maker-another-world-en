"""The item cards in English: the 128x32 box under a shop list (name, price, what it does) and the equipment boxes on
overview page 2 ("Weapon: none" / "Armor: none"). They are pre-drawn 4bpp images, not text: one asset each, 64 tiles
in rows of 16, LZ format 4 (0x800 bytes), reached through the asset table at C9 `$02CD` + 3k (card k = the shop
item list C7 `$041A` entry k + 1; 53 and 54 are the empty weapon and armor boxes). Seen loading with
(overview page 2: C9 `$0440`/`$0443` -> CD `$FCC8`, CE `$0000`).

Each card keeps its frame and background (per pixel row, the commonest colour inside the frame) and gets the English
drawn in the Japanese ink (the club card's commonest colour besides the background; the palette is shared; no shadow): the name on the top line with
the price right-aligned in a 3x5 digit font, the effects on the second line in the English font, or
in two rows of the 5x7 font when they don't fit (narrow lower case from _narrow.py for a long name). Stored raw (format 0) at GFX3 and the table entries repointed."""

import importlib.util
import sys
from collections import Counter
from pathlib import Path

from _layout import GFX3, REPO, put, snes_to_rom
from _narrow import NARROW, narrow_rows

sys.path.insert(0, str(REPO / 'tools' / 'gfx'))

TABLE = 0xC902CD
PRICED = 50  # cards 0-49 have a PRICES entry; 50-52 (the diner's Cake, Meat Dish, Seafood) keep the hand-read price
PRICES = 0xC1D4E6  # word table: entry k + 1 = card k's price in Gold (entry 0 is not a price); Winter Wear 120, as the tailor says
W, H, X0, X1, Y0, Y1 = 128, 32, 3, 100, 2, 29  # the asset, and the inside of the card's frame (inclusive; 104 px shown)

# (name, price, effects) per card, from the Japanese cards (build/cards*.png renders); names as the shop lists' finals.
# A price only says whether the card shows one: the number comes from PRICES
CARDS = [
    ('Club', '15G', 'Attack+3'), ('Bronze Sword', '450G', 'Attack+7'), ('Steel Dagger', '1000G', 'Attack+10'),
    ('Dragon Blade', '2000G', 'Attack+13 Combat-2'), ('Eagle Talon', '5000G', 'Attack+25 Defense-4'),
    ('Thunderblade', '15000G', 'Attack+20 Combat+5'), ('Ice Sword', '25000G', 'Attack+25 Combat+10'),
    ('Light Sword', '30000G', 'Attack+30 Combat+30'), ('Dragon Horn', '35000G', 'Attack+40 Combat-10'),
    ('Royal Sword', '50000G', 'Attack+12 Grace+50'), ('Arian Sword', '50000G', 'Atk+25 Def+10 Combat+18'),
    ('Wolf Armor', '300G', 'Defense+8'), ('Chainmail', '4000G', 'Defense+15 Combat-5'),
    ('Steel Armor', '11000G', 'Defense+20 Combat-10'), ('Mystic Armor', '30000G', 'Defense+25 Magic Def.+15'),
    ('Dwarf Armor', '50000G', 'Def+10 MDef+5 Charm+40'), ('Arian Armor', '25000G', 'Defense+30 Combat+10'),
    ('Casual Wear', '', ''), ('Summer Wear', '700G', ''), ('Winter Wear', '1200G', ''),
    ('Cotton Dress', '5000G', 'Grace+15'), ('Grace Dress', '20000G', 'Grace+40'),
    ('Fierce Dress', '20000G', 'Sensi.+40 Morality-30'), ('Bewitch Dress', '30000G', 'Charm+60 Morality-20'),
    ('Teddy Bear', '1200G', 'Sensi.+10 Stress-40'), ('Rose Cup', '1500G', 'Grace+5'),
    ("Sage's Book", '2000G', 'Intellect+10 Morality+5'), ('Patchwork', '2000G', 'Sensi.+12'),
    ('Potion', '500G', 'Restores HP  One use'), ('Vigor Orb', '500G', 'Restores MP  One use'),
    ('Slim Tea', '5500G', 'Weight-2kg  One use'), ('Mistletoe', '10000G', ''),
    ('Bust Pills', '12000G', 'Bust+2cm  One use'), ('Holy Pendant', '15000G', 'Charm+20 Grace+20'),
    ('Bridal Ring', '50000G', ''), ('High Heels', '12000G', 'Charm+30 Grace+5 Mor-15'),
    ('Time Sand', '8000G', ''), ('Silver Pelt', '8000G', 'Magic Def.+5'),
    ('Evil Star', '15000G', 'Grace+80 Mor-100 Sin+50'), ('Dragon Fang', '22000G', 'Warrior+20'),
    ('Dragon Scale', '7000G', 'Defense+5 Magic Def.+5'), ('Pearl', '8500G', ''), ('Allure Ice', '1000G', 'Charm+5'),
    ('Rose Crown', '25000G', 'Charm+20 Grace+20'), ('Pure Bond', '21000G', 'Art+30 Sensi.+50'),
    ('Golden Egg', '10000G', ''), ('Laughing Bag', '40000G', ''), ('Pointy Shoes', '10000G', ''),
    ('Ultimate Spice', '1000G', ''), ('Demon Ring', '12000G', ''), ('Cake', '800G', 'Stress-50 Weight+1.0kg'),
    ('Meat Dish', '2000G', 'Vigor+15 Weight+1.2kg'), ('Seafood', '1200G', 'Stress-30 Weight+0.4kg'),
    ('Weapon: none', '', ''), ('Armor: none', '', ''),
]


def _ov():
    spec = importlib.util.spec_from_file_location('ov', Path(__file__).with_name('30-overview-labels.py'))
    ov = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ov)
    return ov


def line_glyphs(text, glyphs, widths, room):
    """[(16 row masks, advance)] for `text`, with the narrow lower case if the English font is too wide for `room`."""
    narrow = sum(widths.get(c, 0) for c in text) > room
    out = []
    for c in text:
        if narrow and c in NARROW:
            g, adv = narrow_rows(c)
            out.append((g, adv + 1))
        else:
            out.append((glyphs[c], widths.get(c, 0)))
    if sum(a for _, a in out) > room:
        raise SystemExit(f'item card: {text!r} is {sum(a for _, a in out)} px, the room is {room}')
    return out


TINY = {'0': '###|#.#|#.#|#.#|###', '1': '.#.|##.|.#.|.#.|###', '2': '###|..#|###|#..|###', '3': '###|..#|.##|..#|###',
        '4': '#.#|#.#|###|..#|..#', '5': '###|#..|###|..#|###', '6': '###|#..|###|#.#|###', '7': '###|..#|..#|.#.|.#.',
        '8': '###|#.#|###|#.#|###', '9': '###|#.#|###|..#|###', 'G': '.##|#..|#.#|#.#|.##'}


def tiny_glyphs(text, top_row):
    """[(16 row masks, advance)] in a 3x5 digit font (a price), its rows from `top_row` of the 16."""
    out = []
    for c in text:
        rows = [0] * 16
        for y, r in enumerate(TINY[c].split('|')):
            rows[top_row + y] = sum(0x80 >> x for x, ch in enumerate(r) if ch == '#')
        out.append((rows, 4))
    return out


SMALL_EXTRA = {'.': '.....|.....|.....|.....|.....|.....|..#..', ' ': '.....|.....|.....|.....|.....|.....|.....'}


def small_glyphs(text, sn, top_row):
    """[(16 row masks, advance)] in the 5x7 font of 19-status-name.py, its rows from `top_row` of the 16."""
    out = []
    for c in text:
        pat = (SMALL_EXTRA.get(c) or sn.FONT[c]).split('|')
        rows = [0] * 16
        for y, r in enumerate(pat):
            rows[top_row + y] = sum(0x80 >> x for x, ch in enumerate(r) if ch == '#')
        out.append((rows, 6))
    return out


def wrap_small(text, room):
    """Words of `text` in rows of the 5x7 font (6 px a character) no wider than `room`."""
    rows, cur = [], ''
    for word in text.split():
        cand = f'{cur} {word}' if cur else word
        if len(cand) * 6 - 1 <= room:
            cur = cand
        else:
            rows.append(cur)
            cur = word
    return rows + [cur] if cur else rows


def apply(rom: bytearray) -> None:
    ov = _ov()
    spec = importlib.util.spec_from_file_location('sn', Path(__file__).with_name('19-status-name.py'))
    sn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sn)
    glyphs, widths = ov.font()
    at = GFX3
    for k, (name, price, effects) in enumerate(CARDS):
        if price and k < PRICED:  # what the shop charges and says (the hand-read prices took the card's G mark for a 0)
            o = snes_to_rom(PRICES) + 2 * (k + 1)
            price = f"{int.from_bytes(rom[o:o + 2], 'little')}G"
        entry = TABLE + 3 * k
        o = snes_to_rom(entry)
        addr = int.from_bytes(rom[o:o + 3], 'little')
        q = snes_to_rom(addr)
        if not 0xCD0000 <= addr < 0xCF0000 or rom[q] & 0x0F != 4 or int.from_bytes(rom[q + 1:q + 3], 'little') != 0x800:
            raise SystemExit(f'${entry:06X}: ${addr:06X} is not an item card')
        chr_data = bytearray(ov.asset(rom, addr))
        tiles = [ov.tile_px(chr_data, t) for t in range(64)]
        px = [[tiles[(y // 8) * 16 + x // 8][y % 8][x % 8] for x in range(W)] for y in range(H)]
        bg = [Counter(px[y][X0:X1 + 1]).most_common(1)[0][0] for y in range(H)]
        if k == 0:  # the cards share a palette: the Japanese ink of the first (the club's) serves all; no shadow
            ink = Counter(px[y][x] for y in range(Y0, Y1 + 1) for x in range(X0, X1 + 1)
                          if px[y][x] != bg[y]).most_common(1)[0][0]
        for y in range(Y0, Y1 + 1):
            for x in range(X0, X1 + 1):
                px[y][x] = bg[y]
        room = X1 - X0 + 1
        runs = []  # (top, x, glyphs)
        name_room = room
        if price:
            pg = tiny_glyphs(price, 7)
            pw = sum(a for _, a in pg) - 1
            runs.append((0, X1 + 1 - pw, pg))
            name_room = room - pw - 3
        runs.append((0, X0, line_glyphs(name, glyphs, widths, name_room)))
        if effects:
            if sum(widths.get(c, 0) for c in effects) <= room:
                runs.append((14, X0, line_glyphs(effects, glyphs, widths, room)))
            else:
                rows = wrap_small(effects, room)
                if len(rows) > 2:
                    raise SystemExit(f'item card: {effects!r} needs {len(rows)} rows of the small font')
                for i, r in enumerate(rows):
                    runs.append((15, X0, small_glyphs(r, sn, 8 * i)))  # rows y 15-21, 23-29
        for top, x, gl in runs:
            ink_at = set()
            for g, adv in gl:
                for y in range(16):
                    for gx in range(8):
                        if g[y] & 0x80 >> gx:
                            ink_at.add((top + y, x + gx))
                x += adv
            for y, xx in ink_at:
                if Y0 <= y <= Y1 and X0 <= xx <= X1:
                    px[y][xx] = ink
        for t in range(64):
            ty, tx = t // 16 * 8, t % 16 * 8
            chr_data[t * 32:t * 32 + 32] = ov.px_tile([[px[ty + y][tx + x] for x in range(8)] for y in range(8)])
        blob = bytes([0xA0]) + len(chr_data).to_bytes(2, 'little') + bytes(chr_data)
        if (at & 0xFFFF) + len(blob) > 0x10000:
            at = (at & 0xFF0000) + 0x10000
        put(rom, at, blob)
        rom[o:o + 3] = at.to_bytes(3, 'little')
        at += len(blob)
    print(f'  item cards: {len(CARDS)} in English, to ${at:06X}')
