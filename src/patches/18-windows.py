"""Wider windows for the English: per window group, the descriptors (x, characters a line, rows), the `D5`/`D6` frame
codes that draw and erase the border, and the `E5`/`E6` menu cursor position.

A window's text area comes from a 24-byte descriptor copied by `$87:8EA0` (word 4 x, word 6 characters a line at
12 px each, word 7 tile rows); its border is drawn separately by the script code `D5 x y w h` (BG3 tiles, w x h = the
inside in 8 px tiles) and erased by `D6` with the same arguments
Every `D5`/`D6` with a group's Japanese frame x, y, w (any height when h is None; only in `banks` when given) is
rewritten, and every `E5`/`E6` menu setup with its cursor position. The window's tiles (ceil(chars / 2) * 6 a line,
from its tile base) must stay clear of the next window's: checked against `tile_room` (0 = the descriptor sets its
own line stride, word 11). Each entry is checked against the base ROM bytes, so a wrong address stops the build."""

from collections import Counter

from asm65816 import assemble
from _layout import LIST_CURSOR_CODE, put, snes_to_rom

FRAME_CODES = (0xD5, 0xD6)
MENU_CODES = (0xE5, 0xE6)  # E5/E6 <items> <cursor x> <cursor y> <2 bytes>: the menu cursor's tile position
WORD = {'x': 4, 'chars': 6, 'rows': 7}
SHOP_LISTS = [0x85A8CF, 0x85A8E7, 0x85B2A0, 0x85C54B, 0x85E0F3, 0x85E24D, 0x85EE37, 0x85F2F5, 0x8697DB]

# desc: descriptor addresses; old/new: {x, chars, rows} ('rows' left out of old when it differs per descriptor);
# frame: Japanese (x, y, w, h) -> new; cursor: (x, y) -> (x, y); banks: limit the frame/cursor search
WINDOWS = [
    {'what': 'equipment screen: command menu (Item / Weapon Off / Armor Off / Quit)', 'desc': [0x869025],
     'old': {'x': 3, 'chars': 4, 'rows': 8}, 'new': {'chars': 7},
     'frame': ((1, 9, 8, 8), (1, 9, 11, 8)), 'cursor': None, 'tile_room': 0x100},
    {'what': 'main screen: right-hand menu (talk, topics, ...; 79 uses), grown left; 4 lines, as its frame shows',
     'desc': [0x82AD57], 'old': {'x': 21, 'chars': 7, 'rows': 10}, 'new': {'x': 18, 'chars': 9, 'rows': 8},
     'frame': ((19, 10, 10, None), (16, 10, 13, None)), 'cursor': ((20, 11), (17, 11)), 'tile_room': 0x78},
    {'what': 'shops: item lists (list mode, $400) and the 12 px menus in the same spot, grown 1 tile left (the dialogue box border is at tile 17) and 1 right',
     'desc': SHOP_LISTS + [0x85A608, 0x85A638], 'old': {'x': 21, 'chars': 6}, 'new': {'x': 20, 'chars': 7},
     'frame': ((19, 5, 10, None), (18, 5, 12, None)), 'cursor': ((22, 6), (21, 6)), 'banks': (0xC5, 0xC6),
     'tile_room': 0},
    {'what': 'castle: who to see (gatekeeper, royal guard, general ...), grown 3 tiles left (clear of the dialogue box) and right; cursor one column left of the text, as in the original', 'desc': [0x868136],
     'old': {'x': 23, 'chars': 4, 'rows': 18}, 'new': {'x': 20, 'chars': 6},
     'frame': ((21, 5, 8, None), (18, 5, 11, None)), 'cursor': ((22, 6), (19, 6)), 'banks': (0xC2,),
     'tile_room': 0x100},
    {'what': 'vacation: where to (Mountains / Seaside), grown left to the dialogue box', 'desc': [0xC76A44],
     'old': {'x': 23, 'chars': 4}, 'new': {'x': 19, 'chars': 6},
     'frame': ((22, 11, 4, None), (18, 11, 10, None)), 'cursor': ((23, 12), (19, 12)), 'banks': (0xC7,),
     'tile_room': 0x100},
    {'what': 'quest screens: message box, narrowed: its 14th character ran past the frame and wrapped to column 0', 'desc': [0x8389E8], 'old': {'x': 9, 'chars': 14}, 'new': {'chars': 13},
     'frame': None, 'cursor': None, 'tile_room': 0},
    {'what': "ending: the daughter's letter, narrowed: words ran past its right frame and restarted on the next line",
     'desc': [0xC80EAB], 'old': {'x': 2, 'chars': 18, 'rows': 18}, 'new': {'chars': 17},
     'frame': None, 'cursor': None, 'tile_room': 0},
]


# A list-mode window's cursor ($88:8928) takes its column from $A027 (the list's E5); the shop lists now start
# 1 tile further left, so while window slot 2 holds a list ($9F7F bit $400) the column is 1 less.
CURSOR_HOOK = 0x888928
CURSOR_HOOK_ORIGINAL = bytes.fromhex('AD27A0856C')  # LDA $A027 / STA $6C
CURSOR_CODE = """
list_cursor:
        LDA $7E9F7F         ; window slot 2's flags: a shop list (list mode, $400) is there while its cursor moves
        AND #$0400
        BEQ lc_same
        LDA $7EA027
        SEC
        SBC #$0001          ; the lists start 1 tile further left
        BRA lc_out
lc_same:
        LDA $7EA027
lc_out: STA $6C
        RTL
"""


FRAME_LOOKBACK = 96  # bytes before a menu code searched for the D5 frame its items are drawn in


def in_frame(rom: bytearray, at: int, win: dict) -> bool:
    """Whether the last `D5` before the menu code at `at` is this group's (already rewritten) frame: a cursor at the same
    tile in another menu is left alone (the town menu, E5 86 16 06 at C5 $0077, shares the shop lists' (22, 6))."""
    if not win['frame']:
        return True
    nx, ny, nw, _ = win['frame'][1]
    j = rom.rfind(bytes([0xD5]), at - FRAME_LOOKBACK, at)
    while j != -1 and rom[j + 1:j + 4] != bytes([nx, ny, nw]):
        j = rom.rfind(bytes([0xD5]), at - FRAME_LOOKBACK, j)
    return j != -1


def tiles(chars: int, rows: int) -> int:
    return -(-chars // 2) * 6 * (rows // 2)


def bank_ranges(win: dict) -> list[tuple[int, int]]:
    banks = win.get('banks') or range(0xC0, 0xE0)
    return [(snes_to_rom(b << 16), snes_to_rom(b << 16) + 0x10000) for b in banks]


def apply(rom: bytearray) -> None:
    frames = cursors = 0
    per_group = Counter()
    for win in WINDOWS:
        for desc in win['desc']:
            base = snes_to_rom(desc)
            for field, value in win['old'].items():
                o = base + 2 * WORD[field]
                if rom[o:o + 2] != value.to_bytes(2, 'little'):
                    raise SystemExit(f"${desc:06X}: expected {field} {value} ({win['what']})")
            rows = int.from_bytes(rom[base + 14:base + 16], 'little')
            new = {'rows': rows, **win['old'], **win['new']}
            if win['tile_room'] and tiles(new['chars'], new['rows']) > win['tile_room']:
                raise SystemExit(f"${desc:06X}: {tiles(new['chars'], new['rows'])} tiles > room {win['tile_room']}")
            for field, value in win['new'].items():
                o = base + 2 * WORD[field]
                rom[o:o + 2] = value.to_bytes(2, 'little')
        n = 0
        (ox, oy, ow, oh), (nx, ny, nw, nh) = win['frame'] or ((0, 0, 0, 0), (0, 0, 0, 0))
        for lo, hi in bank_ranges(win) if win['frame'] else []:
            i = lo - 1
            while (i := rom.find(bytes([ox, oy, ow]), i + 1, hi)) != -1:
                if rom[i - 1] in FRAME_CODES and (oh is None or rom[i + 3] == oh):
                    rom[i:i + 3] = bytes([nx, ny, nw])
                    n += 1
        if win['frame'] and not n:
            raise SystemExit(f"no D5/D6 frame {win['frame'][0]} ({win['what']})")
        frames += n
        if win['cursor']:
            (cx, cy), (dx, dy) = win['cursor']
            for lo, hi in bank_ranges(win):
                i = lo - 1
                while (i := rom.find(bytes([cx, cy]), i + 1, hi)) != -1:
                    if rom[i - 2] in MENU_CODES and in_frame(rom, i - 2, win):
                        rom[i] = dx
                        cursors += 1
                        per_group[win['what']] += 1
    o = snes_to_rom(CURSOR_HOOK)
    if rom[o:o + 5] != CURSOR_HOOK_ORIGINAL:
        raise SystemExit(f'${CURSOR_HOOK:06X} is not LDA $A027 / STA $6C')
    code, labels = assemble(LIST_CURSOR_CODE, CURSOR_CODE)
    put(rom, LIST_CURSOR_CODE, code)
    rom[o:o + 5] = bytes([0x22]) + labels['list_cursor'].to_bytes(3, 'little') + b'\xEA'
    print(f'  windows: {len(WINDOWS)} groups resized, {frames} frame codes, {cursors} menu cursors')
    for what, n in per_group.items():
        print(f'    {n:3d} cursors: {what[:60]}')
