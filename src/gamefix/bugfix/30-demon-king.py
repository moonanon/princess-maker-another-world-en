"""The Demon King's bride: the hero ending's tale where she slays a Demon King is never followed by Galbar's proposal.

The ending's results are copied to `$7E:99C2..` at 88:C4A1. Ending 58 (`$99C8` = 58, script C2:6611, the hero
epilogue) tells one of three tales by `$99CA` (`DD 88:97B2` at C2:6950); tale 1 (C2:695D) has her seek out and defeat
the Demon King who cursed the southern capital. The marriage scene is picked by `$99CC` (`DD 88:97B2` at C8:2522,
table 27DB 2C12 2FB7 32C6 35C0): 4 is Galbar, the Demon King, asking for her hand (C8:32C6). `F8 7E:99CC` at
C8:251A skips the marriage scene when it is 0. So with ending 58, tale 1 and partner 4 the partner is set to 0: she
stays single rather than marry the king she killed. Read from the script and code; not seen in play.
"""

from asm65816 import assemble
from _layout import BUGFIX_CODE, put, snes_to_rom

AT = BUGFIX_CODE + 0x100  # after 20-jester.py's code
HOOK = 0x88C4C9  # LDA $7EA5E9 (then STA $7E99CC: the marriage partner)
HOOK_ORIGINAL = bytes.fromhex('AFE9A57E')
CODE = """
partner:                    ; A = the marriage partner the evaluator chose
        LDA $7EA5E9
        CMP #$0004          ; Galbar
        BNE pt_out
        LDA $7EA5E5
        CMP #$003A          ; ending 58, the hero (F5 at C8:2462 indexes id/2: entry 29, C2:6611)
        BNE pt_galbar
        LDA $7EA5E7
        CMP #$0001          ; the tale where she slays the Demon King
        BNE pt_galbar
        LDA #$0000          ; no marriage scene
        RTL
pt_galbar:
        LDA #$0004
pt_out: RTL
"""


def apply(rom: bytearray) -> None:
    o = snes_to_rom(HOOK)
    if rom[o:o + 4] != HOOK_ORIGINAL:
        raise SystemExit(f'${HOOK:06X} is not LDA $7EA5E9')
    code, labels = assemble(AT, CODE)
    put(rom, AT, code)
    rom[o:o + 4] = bytes([0x22]) + labels['partner'].to_bytes(3, 'little')  # JSL
    print('  bugfix: no Demon King proposal after the tale where she slays him')
