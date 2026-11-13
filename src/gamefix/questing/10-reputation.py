"""Going home early from a quest raises the warrior/magic rating by the days actually spent, not every scheduled day.

The go-home script (`C3:0B28` "really go home?" -> yes -> `C3:0B5D` "returned home") ends with `DD 83:9184`, which adds
`$0DA1` (the scheduled quest's days, set at the trip's start by `$83:8089`) to the higher rating.
That DD now calls `early_home`, which caps `$0DA1` at today `$7E:998E` - the slot's first day
`$7E:99B0[$99BE]` + 1 and goes on to `83:9184`. The normal end of a quest is untouched."""

from asm65816 import assemble
from _layout import EARLY_HOME_CODE, put, snes_to_rom

GO_HOME_DD = 0xC30B68  # `DD 84 91 83` in the go-home script
CODE = """
early_home:
        LDA $7E99BE         ; the quest's schedule slot
        ASL A
        TAX
        LDA $7E998E         ; today
        AND #$00FF
        SEC
        SBC $7E99B0,X       ; - the slot's first day
        INC A
        BMI eh_none
        CMP $7E0DA1
        BCS eh_grant        ; stayed the whole time: as scheduled
        BRA eh_set
eh_none:
        LDA #$0000
eh_set: STA $7E0DA1
eh_grant:
        JML $839184         ; adds $0DA1 to the higher rating; its RTL returns to the script engine
"""


def apply(rom: bytearray) -> None:
    o = snes_to_rom(GO_HOME_DD)
    if rom[o:o + 4] != bytes.fromhex('DD849183'):
        raise SystemExit(f'${GO_HOME_DD:06X} is not DD 83:9184')
    code, labels = assemble(EARLY_HOME_CODE, CODE)
    put(rom, EARLY_HOME_CODE, code)
    rom[o + 1:o + 4] = labels['early_home'].to_bytes(3, 'little')
    print(f'  questing: going home early grants the days spent ({len(code)} bytes at ${EARLY_HOME_CODE:06X})')
