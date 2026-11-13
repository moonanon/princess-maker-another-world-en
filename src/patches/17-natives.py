"""The `E1` wait and the native that keeps English lines from hanging it.

`E1` (wait for the scene's animation) zeroes $7E:A00F when it starts and then waits for an animation to raise it. The
Japanese line before it is short enough that the animation always ends after `E1` has started. An English line takes
longer to type, so the animation can finish first and `E1` waits forever (the day-result scenes hung).

`clear_wait` is a native (`DD <address>`, returns with RTL to $87:97CF) that 20-text.py puts at the start of an English
line of a message that goes on to an `E1`: the first one since the last `E1` zeroes $7E:A00F and sets $7F:F060, the
others do nothing (a "Day 2." line before the day's result line: zeroing at the second line lost the animation's pulse
given during the first, and the chores scene hung). `e1_start` replaces `E1`'s first six bytes
(`STZ $A00F / INC $9FF3`): with $7F:F060 set it clears that flag instead of zeroing $A00F, so a rise that happened
while the English was typing still counts. Any other `E1` behaves as before."""

from asm65816 import assemble

from _layout import E1_HOOK_CODE, NATIVE_CLEAR_WAIT, NATIVE_FIT, put, snes_to_rom

E1_START = 0x878FD8
E1_START_ORIGINAL = bytes.fromhex('9C0FA0EEF39F')  # STZ $A00F / INC $9FF3

CLEAR_WAIT = '''
clear_wait:
        PHP
        REP #$20
        LDA $7FF060         ; only the message's first English line clears: a pulse the animation gives while a later
        BNE cw_done         ; line types (or while the first one does) must still count
        STA $7EA00F
        INC A
        STA $7FF060
cw_done:
        PLP
        RTL
'''

E1_START_CODE = '''
e1_start:
        PHP
        REP #$20
        LDA $7FF060
        BEQ e1_zero
        LDA #$0000
        STA $7FF060
        BRA e1_next
e1_zero:
        LDA #$0000
        STA $7EA00F
e1_next:
        LDA $7E9FF3
        INC A
        STA $7E9FF3
        PLP
        RTL
'''

FIT = '''
fit:                        ; DD fit <px> <fallback>: the script pointer is at <px>
        PHP
        REP #$30
        STZ $6C
        LDA $7E9FF1
        AND #$00FF
        STA $6E
        LDA $7E9FEF
        TAY
        LDA $7E9FC5
        TAX
        LDA $7E9F7D,X       ; not a 12 px window (the VWF draws only there): the Japanese
        AND #$0040
        BEQ fit_no
        LDA $7E9FA1,X       ; room left on the line: (characters a line - column) * 12 px; a full line (column at
        SEC                 ; the limit) is a fresh one: the game wraps before the next character
        SBC $7E9FD1,X
        BEQ fit_full
        BPL fit_room
fit_full:
        LDA $7E9FA1,X
fit_room:
        ASL A
        ASL A
        STA $7FF070
        ASL A
        CLC
        ADC $7FF070
        STA $7FF070
        LDA [$6C],Y         ; the English's width in px
        AND #$00FF
        CMP $7FF070
        BEQ fit_yes
        BCS fit_no
fit_yes:
        TYA
        CLC
        ADC #$0004
        STA $7E9FEF         ; skip <px> <fallback>: the English follows
        PLP
        RTL
fit_no:
        INY
        LDA [$6C],Y         ; the fallback: a copy of the Japanese
        STA $7E9FEF
        INY
        INY
        LDA [$6C],Y
        AND #$00FF
        STA $7E9FF1
        PLP
        RTL
'''


def apply(rom: bytearray) -> None:
    code, _ = assemble(NATIVE_FIT, FIT)
    put(rom, NATIVE_FIT, code)
    code, _ = assemble(NATIVE_CLEAR_WAIT, CLEAR_WAIT)
    put(rom, NATIVE_CLEAR_WAIT, code)
    code, labels = assemble(E1_HOOK_CODE, E1_START_CODE)
    put(rom, E1_HOOK_CODE, code)
    off = snes_to_rom(E1_START)
    if rom[off:off + 6] != E1_START_ORIGINAL:
        raise SystemExit(f'${E1_START:06X} is not the expected STZ $A00F / INC $9FF3')
    rom[off:off + 6] = bytes([0x22]) + labels['e1_start'].to_bytes(3, 'little') + b'\xEA\xEA'
