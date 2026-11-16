"""Defeating a peaceful person on a quest costs 30 Morality, the game's own penalty (`$82:88EC` takes 30 from Morality
`$7E:9466`, floor 0, and prints `C0:529B` "Morality fell by 30").

Peaceful people: 12 traveller, 13 mage, 15 soldier. Bandits (7), kidnappers (14)
and outlaws (16, 17) can be fought freely; the named people (23-34) are the tournament's, not the quests'.
When a quest battle ends with the enemy beaten, `$83:9BB7` points the script at `C3:1561` ("[enemy] was defeated...").
Asking a peaceful person for nothing  no longer starts a fight: `83:852D` grades the demand and a grade of 0
means `INC $0D86` (battle) whatever was asked. `nothing_asked` turns grade 0
into 1, the game's own accepting path, for Nothing to a peaceful id.
That pointer setup is now a JSL to `people_defeated`: for a peaceful id it lowers Morality and points the script at
`defeated_person`, which calls the game's own defeat line and then shows "[name]'s Morality fell by 30."
"""

from asm65816 import assemble
from en_text import encode
from _layout import QUESTING_CODE, put, snes_to_rom

NOTHING_HOOK = 0xC38537  # STA $0D84 / CMP #$0000 after `83:8F96` grades the demand (grade 0 -> INC $0D86, a fight)
NOTHING_ORIGINAL = bytes.fromhex('8D840DC90000')
NOTHING = 2  # the demand menu's Nothing (`$A031`)
LIFE = 1  # Life: taking a peaceful person's life costs 30 Morality; a refused demand still fights
HOOK = 0xC39BB7  # LDA #$1561 / STA $7E9FEF / LDA #$00C3 / STA $7E9FF1 (14 bytes)
HOOK_ORIGINAL = bytes.fromhex('A961158FEF9F7EA9C3008FF19F7E')
PEACEFUL = (12, 13, 15)
MESSAGE = "'s Morality fell by 30."
# Wait, then `FC 00`: with nothing pending FC hands control back to the game, which reads the next byte as its
# command; the defeat line (C3:1561) and the peaceful people's Life lines all end `FC 00`.
END = bytes([0xD8, 0xFC, 0x00])


LIFE_HOOK = 0xC38684  # in `83:8659`: TAY / LDA #$00C3 / JSL $87:820D (the daughter's demand line)
LIFE_HOOK_ORIGINAL = bytes.fromhex('A8A9C300220D8287')


def life_message() -> bytes:
    """After her demand line: a new page, "[name]'s Morality fell by 30.", wait, `FC 00`."""
    return bytes([0xD8, 0xDA, 0xDE]) + (0x7E0EE8).to_bytes(3, 'little') + encode(MESSAGE) + END


def script(at: int) -> bytes:
    """Window 0 (a started script opens with its window byte, as C3:1561 does), call the game's defeat line past its
    window byte (C3:1562), then a new page: her name + the penalty message, wait, `FC 00`."""
    return (bytes([0x00, 0xDE]) + (0xC31562).to_bytes(3, 'little') + bytes([0xD8, 0xDA, 0xDE]) +
            (0x7E0EE8).to_bytes(3, 'little') + encode(MESSAGE) + END)


def code(script_at: int, msg_at: int = 0) -> str:
    checks = '\n'.join(f'        CMP #${p:04X}\n        BEQ pd_person' for p in PEACEFUL)
    return f"""
nothing_asked:              ; A = the demand's grade (0 = refused: a fight)
        CMP #$0000
        BEQ na_refused
        PHA                 ; accepted: Life from a peaceful person costs 30 Morality
        LDA $7EA031
        CMP #${LIFE:04X}
        BNE na_kept
        LDA $7E0DD9
{checks.replace('pd_person', 'na_life')}
        BRA na_kept
na_life:
        LDA $7E9466
        SEC
        SBC #$001E
        BPL na_lstore
        LDA #$0000
na_lstore:
        STA $7E9466
        LDA #$0001
        STA $7FF0F0         ; the demand line shows the penalty (life_line)
na_kept:
        PLA
        BRA na_store
na_refused:
        LDA $7EA031         ; the demand: Nothing?
        CMP #${NOTHING:04X}
        BNE na_zero
        LDA $7E0DD9
{checks.replace('pd_person', 'na_peaceful')}
na_zero:
        LDA #$0000
        BRA na_store
na_peaceful:
        LDA #$0001          ; accepted: they go on their way
na_store:
        STA $7E0D84
        CMP #$0000          ; flags for the game's BEQ
        RTL

life_line:                  ; A = the daughter's demand line in bank C3 (as at `83:8684`), on to JSL $87:820D
        TAY
        LDA $7FF0F0
        BEQ ll_plain
        LDA #$0000
        STA $7FF0F0
        TYX                 ; a RAM script, as a started script must be: window byte (her line's first), then
        LDA $C30000,X       ; DE <her line past it>, then DF <the penalty message> (in ROM)
        AND #$00FF
        ORA #$DE00
        STA $7FF0E0         ; E0 window, E1 DE
        TYA
        INC A
        STA $7FF0E2         ; E2-E3 the line past its window byte
        LDA #$DFC3
        STA $7FF0E4         ; E4 bank C3, E5 DF
        LDA #${msg_at & 0xFFFF:04X}
        STA $7FF0E6
        LDA #${msg_at >> 16:04X}
        STA $7FF0E8
        LDY #$F0E0
        LDA #$007F
        JML $87820D
ll_plain:
        LDA #$00C3
        JML $87820D

people_defeated:
        LDA $7E0DD9         ; the enemy id
{checks}
        LDA #$1561          ; anyone else: the game's own defeat line
        STA $7E9FEF
        LDA #$00C3
        STA $7E9FF1
        RTL
pd_person:
        LDA $7E9466         ; Morality - 30, not below 0 (as $82:88EC)
        SEC
        SBC #$001E
        BPL pd_store
        LDA #$0000
pd_store:
        STA $7E9466
        LDA #${script_at & 0xFFFF:04X}
        STA $7E9FEF
        LDA #${script_at >> 16:04X}
        STA $7E9FF1
        RTL
"""


def apply(rom: bytearray) -> None:
    o = snes_to_rom(HOOK)
    if rom[o:o + len(HOOK_ORIGINAL)] != HOOK_ORIGINAL:
        raise SystemExit(f'${HOOK:06X} is not the defeat-line pointer setup')
    size = len(assemble(QUESTING_CODE, code(QUESTING_CODE, QUESTING_CODE))[0])
    script_at = QUESTING_CODE + size
    msg_at = script_at + len(script(script_at))
    asm, labels = assemble(QUESTING_CODE, code(script_at, msg_at))
    put(rom, QUESTING_CODE, asm)
    put(rom, script_at, script(script_at))
    put(rom, msg_at, life_message())
    h = snes_to_rom(LIFE_HOOK)
    if rom[h:h + 8] != LIFE_HOOK_ORIGINAL:
        raise SystemExit(f'${LIFE_HOOK:06X} is not TAY / LDA #$00C3 / JSL $87:820D')
    rom[h:h + 8] = bytes([0x22]) + labels['life_line'].to_bytes(3, 'little') + b'\xEA' * 4
    n = snes_to_rom(NOTHING_HOOK)
    if rom[n:n + len(NOTHING_ORIGINAL)] != NOTHING_ORIGINAL:
        raise SystemExit(f'${NOTHING_HOOK:06X} is not STA $0D84 / CMP #0')
    rom[n:n + 6] = bytes([0x22]) + labels['nothing_asked'].to_bytes(3, 'little') + b'\xEA\xEA'
    rom[o:o + len(HOOK_ORIGINAL)] = bytes([0x22]) + labels['people_defeated'].to_bytes(3, 'little') + b'\xEA' * 10
    print(f'  questing: peaceful people: no fight over Nothing; defeating one costs 30 Morality (ids {PEACEFUL}, ${QUESTING_CODE:06X})')
