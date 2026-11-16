"""The young dragon's bride: a father who gives his blessing at the dragons' visit makes the dragon's marriage reachable.

The evaluator's partner 5 (88:D8A5, flag `$A619`) is set from `$7E:9934` at 88:C684, and its scene C8:35C0 has the
young dragon come for her "as promised". Nothing in the game ever writes `$9934`. The young dragon's visit (script
C0:4C46..) asks the father to give her away for a 10000 Gold gift: "Allow It" runs `DD 82:88EC` at C0:5274 (the gold,
Morality -30), "Refuse" never does. So the call at C0:5274 goes to `blessing`, which sets `$9934` and carries on to
82:88EC. Seen in Mesen: with `$9934` = 1 the ending plays C8:35E9..C8:3715.
"""

from asm65816 import assemble
from _layout import BUGFIX_CODE, put, snes_to_rom

AT = BUGFIX_CODE + 0x180  # after 30-demon-king.py's code
CALL = 0xC05275  # the 24-bit address of `DD 82:88EC` in the Allow It branch
CALL_ORIGINAL = bytes.fromhex('EC8882')
CODE = """
blessing:
        LDA #$0001
        STA $7E9934         ; the young dragon will come back for her
        JML $8288EC         ; the gift, as before (it ends in RTL)
"""


def apply(rom: bytearray) -> None:
    o = snes_to_rom(CALL)
    if rom[o:o + 3] != CALL_ORIGINAL:
        raise SystemExit(f'${CALL:06X} is not the call to 82:88EC')
    code, labels = assemble(AT, CODE)
    put(rom, AT, code)
    rom[o:o + 3] = labels['blessing'].to_bytes(3, 'little')
    print('  bugfix: the father\'s blessing at the dragons\' visit makes the young dragon\'s marriage reachable')
