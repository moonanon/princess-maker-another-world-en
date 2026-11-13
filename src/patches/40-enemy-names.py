"""Quest and tournament opponents' names in English (the name in battle lines, the speaker tag, "[name] appeared!").

`83:BA69` copies 13 bytes of the name from the word pointer `$83:BAA1` + (id-1)*2 (bank $83) into RAM `$7E:0DDB`,
which the script prints with `DE 7E:0DDB`. One-byte codes printed from `$7E:0D00-0FFF` are drawn by the VWF through
NAME_MAP (15-vwf.py, the daughter's name), so the English names are one byte a letter in those codes: at most 12
letters + `FC`. The new strings go in bank $C3 at `C3:FE00` (zero-filled, after the bank's code; it must be at $8000+ since the copier reads bank $83)."""

import importlib.util
from pathlib import Path

from _layout import put, snes_to_rom

TABLE = 0xC3BAA1
AT = 0xC3FE00
SPACE = 0x50  # a one-byte code no name-entry cell uses: a space in an English name
NAMES = ['Red Dragon', 'Blue Dragon', 'White Dragon', 'Merman', 'Harpy', 'Demon', 'Bandit', 'Banshee', 'War God',
         'Wolf', 'Silver Wolf', 'Traveler', 'Mage', 'Kidnapper', 'Soldier', 'Outlaw', 'Outlaw', 'Fang Rabbit',
         'Sand Clam', 'Young Dragon', 'Old Dragon', 'Ghost Knight', 'Rosalie', 'Leon', 'Lian', 'Medinia', 'Jogja',
         'Bathurst', 'Legion', 'Yuri', 'Pugachev', 'Negros', 'Marta', 'Marie']


def codes() -> dict[str, int]:
    spec = importlib.util.spec_from_file_location('vwf', Path(__file__).with_name('15-vwf.py'))
    vwf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vwf)
    return {ch: c for c, ch in zip(vwf.GRID_CODES, vwf.GRID_LETTERS)}


def apply(rom: bytearray) -> None:
    letter = codes()
    if SPACE in letter.values():
        raise SystemExit(f'space code ${SPACE:02X} is a name-entry cell')
    nm = snes_to_rom(0xDB0B00 + SPACE)  # NAME_MAP: written by 15-vwf.py, the space left 0
    if rom[nm]:
        raise SystemExit('NAME_MAP space slot already set')
    rom[nm] = ord(' ')
    blob, at = bytearray(), AT
    for i, name in enumerate(NAMES):
        if len(name) > 12:
            raise SystemExit(f'{name!r}: the copier takes 12 letters + FC')
        s = bytes(SPACE if ch == ' ' else letter[ch] for ch in name) + b'\xFC'
        s += bytes(13 - len(s))  # the copier always reads 13 bytes
        t = snes_to_rom(TABLE + 2 * i)
        if not 0x8000 <= int.from_bytes(rom[t:t + 2], 'little'):
            raise SystemExit(f'${TABLE + 2 * i:06X} is not a name pointer')
        rom[t:t + 2] = ((at & 0xFFFF) + len(blob)).to_bytes(2, 'little')
        blob += s
    put(rom, AT, bytes(blob))
    print(f'  enemy names: {len(NAMES)} in English at ${AT:06X}')
