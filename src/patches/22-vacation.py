"""The vacation line in English as one sentence: "You and your daughter spent the <season> in the <mountains|seaside>."

The Japanese (`C7:6CE5`) is {D2}{D1}"father and daughter" + jump table `F2 7E:9994` (5 targets: spring spring summer autumn winter, each `DF` to
`C7:6D17` "no") + `F2 7E:A639` (mountains `C7:6D20`, which jumps to `C7:6D28`, the middle of the sea run `C7:6D26`; sea) + "went off
 to play..." then `C7:6D35` (DD, wait, end). A detour on the sea run puts its DF where the mountains run's jump lands, so the run-by-run
insert broke the screen. Here `C7:6CE5` jumps to a copy of the structure in English (`AT`), with both tables, and on
to `C7:6D35`. Runs after 20-text.py and overwrites its detour at `C7:6CE5`."""

from en_text import encode
from _layout import put, snes_to_rom

START = 0xC76CE5
AFTER = 0xC76D35
AT = 0xFE0000  # zero-filled expansion bank, past the text allocator's banks in use
DF = 0xDF


def jump(to: int) -> bytes:
    return bytes([DF]) + to.to_bytes(3, 'little')


def apply(rom: bytearray) -> None:
    o = snes_to_rom(START)
    if rom[o] != DF and rom[o:o + 2] != bytes([0xD2, 0xD1]):  # a detour (draft builds) or the Japanese ({D2}{D1}...)
        raise SystemExit(f'${START:06X} is neither 20-text.py\'s detour nor the Japanese line')
    if rom[snes_to_rom(0xC76CF1):snes_to_rom(0xC76CF5)] != bytes.fromhex('F294997E') or \
            rom[snes_to_rom(0xC76D18):snes_to_rom(0xC76D1C)] != bytes.fromhex('F239A67E'):
        raise SystemExit('vacation jump tables not where expected')
    head = bytes([0xD2, 0xD1]) + encode('You and your daughter spent the') + bytes([0x01, 0x20])
    seasons = ['spring', 'spring', 'summer', 'autumn', 'winter']
    places = ['mountains.', 'seaside.']
    # layout: head, F2 table (F2 + 24-bit RAM pointer + 2*5), season pieces, place table (4 + 2*2), place pieces
    season_tbl = AT + len(head)
    at = season_tbl + 4 + 2 * len(seasons)
    season_at = []
    body = [encode(s) + bytes([0x01, 0x20]) + encode('in the') + bytes([0x01, 0x20]) for s in seasons]
    for b in body:
        season_at.append(at)
        at += len(b) + 4
    place_tbl = at
    at += 4 + 2 * len(places)
    place_at, pbody = [], [encode(p) for p in places]
    for b in pbody:
        place_at.append(at)
        at += len(b) + 4
    out = bytearray(head)
    out += bytes.fromhex('F294997E') + b''.join((a & 0xFFFF).to_bytes(2, 'little') for a in season_at)
    for b in body:
        out += b + jump(place_tbl)
    out += bytes.fromhex('F239A67E') + b''.join((a & 0xFFFF).to_bytes(2, 'little') for a in place_at)
    for b in pbody:
        out += b + jump(AFTER)
    assert AT + len(out) == at, (hex(AT + len(out)), hex(at))
    put(rom, AT, bytes(out))
    rom[o:o + 4] = jump(AT)
    print(f'  vacation line: one English sentence at ${AT:06X} ({len(out)} bytes)')
