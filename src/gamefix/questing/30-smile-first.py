"""The approach menu lists Smile first (the cursor starts on the friendly choice): Scare / Smile become Smile / Scare.

The menu (`C3:003F`: Scare at `C3:0040`, Smile at `C3:0047`) is inserted by src/patches/20-text.py as two DF
detours; here each detour is pointed at a new English item with the same resume address, so only the words swap.
The game reads the choice at `83:8449` (`LDA $A031 / STA $0D8A`: 0 Scare, 1 Smile); that is now a JSL to `flip`,
which turns the new order back into the game's before anything reads it."""

from asm65816 import assemble
from en_text import encode
from _layout import put, snes_to_rom

AT = 0xDB1A00  # code + the two items (after 20-people.py's block at $DB:1800)
CHOICE = 0xC38449
CHOICE_ORIGINAL = bytes.fromhex('AD31A08D8A0D')
FIRST, SECOND = 0xC30040, 0xC30047  # the items' script runs (DF detours after 20-text.py)
FIRST_RESUME, SECOND_RESUME = 0xC30046, 0xC3004C
CODE = """
flip:
        LDA $7EA031         ; menu row 0 = Smile now, row 1 = Scare: the game's 0 = Scare, 1 = Smile
        EOR #$0001
        STA $7EA031
        STA $7E0D8A
        RTL
"""


def item(lead: bytes, word: str, resume: int) -> bytes:
    return lead + encode(word) + bytes([0xDF]) + resume.to_bytes(3, 'little')


def lead_of(rom: bytearray, detour: int, word: str) -> bytes:
    """The bytes 20-text.py put before `word` in the item the detour at `detour` jumps to (its row and spacing codes)."""
    o = snes_to_rom(detour)
    target = snes_to_rom(int.from_bytes(rom[o + 1:o + 4], 'little'))
    at = rom.find(encode(word), target, target + 32)
    if at < 0:
        raise SystemExit(f'no {word!r} in the item ${detour:06X} jumps to')
    return bytes(rom[target:at])


def apply(rom: bytearray) -> None:
    c = snes_to_rom(CHOICE)
    if rom[c:c + 6] != CHOICE_ORIGINAL:
        raise SystemExit(f'${CHOICE:06X} is not LDA $A031 / STA $0D8A')
    for a in (FIRST, SECOND):
        if rom[snes_to_rom(a)] != 0xDF:
            raise SystemExit(f'${a:06X} is not an English detour (20-text.py)')
    code, labels = assemble(AT, CODE)
    put(rom, AT, code)
    first = item(lead_of(rom, FIRST, 'Scare'), 'Smile', FIRST_RESUME)
    second = item(lead_of(rom, SECOND, 'Smile'), 'Scare', SECOND_RESUME)
    at1 = AT + len(code)
    at2 = at1 + len(first)
    put(rom, at1, first)
    put(rom, at2, second)
    for a, to in ((FIRST, at1), (SECOND, at2)):
        o = snes_to_rom(a)
        rom[o + 1:o + 4] = to.to_bytes(3, 'little')
    rom[c:c + 6] = bytes([0x22]) + labels['flip'].to_bytes(3, 'little') + b'\xEA\xEA'
    print('  questing: the approach menu lists Smile first')
