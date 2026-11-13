"""The demon deal (quest cave, C3 `$4AC0`-`$5070`): signing outright no longer pays a leftover sum of gold, and once
she has signed the demon never appears again. Signing for his 500 or 1000 Gold still gives the gold and the contract
(stats, Sin, Morality), as the original's second copy of the scene prints.

Script: the choice `F0 <C3:4C12 sign> <C3:4F3A don't>`; don't -> 500 G offer -> 1000 G offer (natives `83:E1EC` /
`83:E1F3` set the amount in `$0E60`), signing for either jumps into a second copy of the signing scene at C3 `$4D3B`;
refusing all three starts a fight (`DD 83:E1E8`). Both copies run `DD 83:DE84` (pay `$0E60` Gold: `JSL $81:E93E`) and
then print and apply Charm/Grace/Magic +50, Sin (`$946A`) +100, Morality 0 (`DD 84:810A`, `84:805F`, `84:80E4`,
`84:8039`, `84:81CB`). So the original pays a stale `$0E60` for a free signature and gives the stats on top of the gold.
The event is offered by `83:DB68` (chance 40% - `$9468`/10, at least 5%) unless `$0E70` bit `$20` is set, and that
flag is cleared every month (`C1:B47F`), so the demon came back.
Fixed: copy 1 calls `deal_made` instead of paying; copy 2's payment (`C3:4DD3`) calls `pay_made`, which pays as
before and then marks the deal. `deal_made` sets bit 0 of
`$7E:99F8` (in the saved block `$9456`-`$9A31`; no code in the ROM touches it, no writes seen in five states), and the
event check also refuses when it is set. Read from the script and code; not seen in play."""

from asm65816 import assemble
from _layout import BUGFIX_CODE, put, snes_to_rom

FLAG = 0x7E99F8
CHECK_HOOK = 0xC3DB94  # LDA #$0020 / BIT $0E70 (then BNE: no event)
CHECK_ORIGINAL = bytes.fromhex('A920002C700E')
CODE = f"""
deal_made:                  ; DD native (no arguments): the deal is made, the demon never comes back
        LDA ${FLAG:06X}
        ORA #$0001
        STA ${FLAG:06X}
        RTL
pay_made:                   ; DD native: copy 2's payment, then the deal is made
        JSL $83DE84
        LDA ${FLAG:06X}
        ORA #$0001
        STA ${FLAG:06X}
        RTL
deal_check:                 ; Z clear = no demon this time (the game's BNE)
        LDA ${FLAG:06X}
        AND #$0001
        BNE dc_out
        LDA $7E0E70
        AND #$0020
dc_out: RTL
"""


def apply(rom: bytearray) -> None:
    o = snes_to_rom(0xC34E13)
    if rom[o:o + 4] != bytes.fromhex('DD0A8184'):
        raise SystemExit('demon deal: copy 2 stat natives not at C3:4E13')
    code, labels = assemble(BUGFIX_CODE, CODE)
    put(rom, BUGFIX_CODE, code)
    made = labels['deal_made']
    o = snes_to_rom(0xC34CA9)  # copy 1: pay $0E60 -> deal_made
    if rom[o:o + 4] != bytes.fromhex('DD84DE83'):
        raise SystemExit('demon deal: C3:4CA9 is not DD 83:DE84')
    rom[o:o + 4] = bytes([0xDD]) + made.to_bytes(3, 'little')
    o = snes_to_rom(0xC34DD3)  # copy 2: pay, then mark the deal
    if rom[o:o + 4] != bytes.fromhex('DD84DE83'):
        raise SystemExit('demon deal: C3:4DD3 is not DD 83:DE84')
    rom[o:o + 4] = bytes([0xDD]) + labels['pay_made'].to_bytes(3, 'little')
    o = snes_to_rom(CHECK_HOOK)
    if rom[o:o + 6] != CHECK_ORIGINAL:
        raise SystemExit(f'demon deal: ${CHECK_HOOK:06X} is not LDA #$20 / BIT $0E70')
    rom[o:o + 6] = bytes([0x22]) + labels['deal_check'].to_bytes(3, 'little') + b'\xEA\xEA'
    print('  bugfix: demon deal (no leftover gold for a plain signature, never again after a deal)')
