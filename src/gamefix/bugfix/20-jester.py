"""After the jester's farewell he is no longer at the castle.

The castle's who-to-see menu picks one of four item lists (`F0` at C2 `$01CF`: base / + Young Officer / + Jester /
both) from `$A031`, set by native `86:842C`: the Jester is listed while `$7E:970E` < 22. His home visits are staged
by `$7E:97EC` (`82:AA07`...): visit 1 at `$970E` >= 7, visit 2 at >= 14, the farewell (C1 `$5C35`, "I've come to say
goodbye") at >= 21 sets it to 3. So for `$970E` = 21 after the farewell he could still be visited. `86:842C` now drops the
Jester from the list once `$97EC` >= 3 (the game's own lists without him: 2 -> 0, 3 -> 1). From the code; not seen in
play (needs a save in that window)."""

from asm65816 import assemble
from _layout import BUGFIX_CODE, put, snes_to_rom

AT = BUGFIX_CODE + 0x80  # after 10-demon-deal.py's code
HOOK = 0xC6846B  # STA $7EA031 / RTL (the list index)
HOOK_ORIGINAL = bytes.fromhex('8F31A07E6B')
CODE = """
castle_list:                ; A = the list index (2/3 = with the Jester)
        CMP #$0002
        BCC cl_store
        PHA
        LDA $7E97EC         ; the jester's visits: 3 = he said farewell
        CMP #$0003
        PLA
        BCC cl_store
        SEC
        SBC #$0002          ; the same list without him
cl_store:
        STA $7EA031
        RTL
"""


def apply(rom: bytearray) -> None:
    o = snes_to_rom(HOOK)
    if rom[o:o + 5] != HOOK_ORIGINAL:
        raise SystemExit(f'${HOOK:06X} is not STA $7EA031 / RTL')
    code, labels = assemble(AT, CODE)
    put(rom, AT, code)
    rom[o:o + 4] = bytes([0x5C]) + labels['castle_list'].to_bytes(3, 'little')  # JML (the RTL there goes unused)
    print('  bugfix: no jester at the castle after his farewell')
