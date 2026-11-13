"""English letters in the text engine: codes $0100-$01FF (low byte = ASCII) drawn by a variable-width font.

The character reader ($87:8403) sends codes $D0-$3FF to the control dispatch, and $FD-$3FF have no handler
(the table at $87:848A stops at FC), so the script never uses them. The hook at $87:841E sends $0100-$01FF to
`vwf_letter` instead. That routine keeps a pixel cursor and a 16-row 1bpp column buffer, ORs each glyph into
it at its pixel offset, and draws 8 px columns of two tiles (top, bottom) through the game's own 1bpp->2bpp
routine ($87:98F1) and DMA queue ($87:8004), writing the window's tilemap the way $87:862B does.

Layout per line (12 px window mode, `$9F7D,X` bit $40): column k of the line uses tiles T+2k and T+2k+1 from
the line's first tile, 21 columns = the 42 tiles the game gives a line.
The game's own state is kept consistent: `$9FE3,X` (tile cursor) moves past every column drawn,
`$9FD1,X` (column, in 12 px characters) becomes ceil(px / 12), so a newline (DB) or a new page (DA),
which reset the column, are seen as a fresh line.

Codes $0101-$011F are blanks of 1-31 px (the space glyph's blank rows, its own advance): the build's exact indent.

Bank-87 routines end in RTS, so they are called with a return address of $87:8002 pushed: RTS lands on
the RTL at $87:8003, which returns to our JSL.
"""

from asm65816 import assemble

from _layout import CODE, FONT, FONT_COUNT, GRID_MAP, NAME_MAP, WIDTHS, WINDOW_SETUP_CODE_AT, put, snes_to_rom

GRID_LO, GRID_HI = 0xC710AE, 0xC710F3  # the name-entry grid's one-byte codes (C7:10AE, 6 rows of 12 + the back/done cells)
# The grid's cells in order (the code picking a cell stores) and what each stands for. Its window draws 16 px cells, so
# the grid shows the Japanese font's own Latin glyphs (upper case and digits only); names in text are drawn by the VWF,
# letters as typed (a-z from 16-name-entry.py's glyphs).
GRID_CODES = bytes.fromhex('090e13181d22272c3237393c 0a0f14191e23282d33873a3d 0b10151a1f24292e3485313e '
                           '0c11161b20252a2f3586893f 0d12171c21262b30363808 40 8c8d8e8f84888a8b4241')
GRID_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!?-+().\''  # then back, done (two-byte codes, not in the list)
LOWER_GLYPHS = {ch: 0x0800 + i for i, ch in enumerate("abcdefghijklmnopqrstuvwxyz'")}  # 16-name-entry.py draws them
JP_GLYPH = {**{c: 0x66 + i for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}, **{c: 0x5C + i for i, c in enumerate('0123456789')},
            '!': 0x87, '?': 0x84, '(': 0x8C, ')': 0x8D, '+': 0x8E, '-': 0x8F, '.': 0x0742, ' ': 0x08, **LOWER_GLYPHS}

MARGIN = 2  # px between a 12 px window's frame and the first letter of a line
HOOK = 0x87841E
HOOK_ORIGINAL = bytes.fromhex('C9D0009030')  # CMP #$00D0 / BCC $8453

# $7F:F000 state (DB = $7F inside the routine)
SOURCE = f'''
en_hook:                    ; M16 X16; A = code, Y = script pointer past it, a PHB on the stack
        CMP #$00D0
        BCC eh_low
        JMP eh_high
eh_low: JSR name_map
        BCS eh_named
        JML $878453         ; a character: the game's path
eh_named:                   ; carry from name_map: V clear = an English letter for a name (A = $01xx), V set = the
        BVS eh_grid         ; grid's own glyph (A = a one-byte code for the game's path)
        PLB
        STY $9FEF
        JSL vwf_letter
        JML $878452
eh_grid:
        STA $7E9FFB         ; the game's path reads the code from here
        JML $878453

name_map:                   ; A = a one-byte code, Y past it. Carry clear: not remapped (A kept)
        PHX                 ; names in RAM $7E:0D00-0FFF -> English letters (VWF), the first of a word upper case;
        PHA                 ; the name-entry grid (C7) -> the Japanese font's own Latin glyphs, 16 px cells as drawn
        LDA $7E9FF1
        AND #$00FF
        CMP #$00C7
        BNE nm_not_c7
        JMP nm_c7
nm_no1: PLA                 ; (an exit within branch range of the RAM checks)
        PLX
        CLC
        RTS
nm_not_c7:
        CMP #$007E
        BNE nm_no1
        CPY #$A028          ; a number the game printed into $7E:A027 (88:8A52): digits by the VWF too
        BCC nm_name
        CPY #$A031
        BCS nm_no1
        BRA nm_win
nm_name:
        CPY #$0D01          ; a name ($7E:0D00-0FFF)
        BCC nm_no1
        CPY #$1001
        BCS nm_no1
nm_win: PHX                 ; a 12 px window (bit $40): the VWF; a 16 px window (name entry's name line): the
        LDA $7E9FC5         ; grid's Japanese-font Latin glyphs
        TAX
        LDA $7E9F7D,X
        AND #$0040
        BEQ nm_w16
        PLX
        BRA nm_ram
nm_w16: PLX
        JMP nm_glyph
nm_ram: PLA
        PHA
        TAX
        LDA ${NAME_MAP:06X},X
        AND #$00FF
        BEQ nm_no1
nm_out: ORA #$0100
        PLX
        PLX
        CLV
        SEC
        RTS
nm_c7:  CPY #${GRID_LO + 1 & 0xFFFF:04X}
        BCC nm_no
        CPY #${GRID_HI + 1 & 0xFFFF:04X}
        BCS nm_no
nm_glyph:
        PLA
        PHA
        ASL A
        TAX
        LDA ${GRID_MAP:06X},X
        BEQ nm_no
        PLX
        PLX
        SEP #$40            ; V set: the game's path
        SEC
        RTS
nm_no:  PLA
        PLX
        CLC
        RTS

eh_high:
        CMP #$0100
        BCC eh_ctl
        CMP #$0200
        BCS eh_ctl
        CMP #$0100          ; $0100, a soft space (the build puts one before each English run): a space only
        BNE eh_notsoft      ; where the run goes on a line after other English (not at a line start, not after a space)
        JSL vwf_soft
        BCC eh_soft
        PLB                 ; nothing to draw: on with the script
        STY $9FEF
        JML $878452
eh_soft:
        LDA #$0120
eh_notsoft:
        CMP #$0120          ; a space: does the next word fit on this line?
        BNE eh_draw
        PHA                 ; the game's DB code below wants X (the window) as the engine left it
        PHX
        PHY
        JSL vwf_wrap
        PLY
        PLX
        PLA
        BCC eh_draw
        LDA #$00DB          ; no: the space becomes the game's own new line (DB), page logic and all
        STA $7E9FFB
        JML $878428
eh_draw:
        PHA                 ; a letter on an overfull line (column past the limit, after a padded list entry): the
        PHX                 ; game's new line first, then this letter again, as the game does for its own
        LDA $7E9FC5
        TAX
        LDA $7E9FA1,X       ; past the limit only (a padded entry; word-wrapped text ends at or under it)
        CMP $7E9FD1,X
        PLX
        PLA
        BCS eh_fits
        DEY
        DEY
        LDA #$00DB
        STA $7E9FFB
        JML $878428
eh_fits:
        PLB                 ; as $87:8469 does for a character
        STY $9FEF
        JSL vwf_letter
        LDA $7E9FC5         ; in a 16 px window (the opening narration) a letter costs no text delay: the next
        TAX                 ; code runs at once, as after D1 ($87:985C). Its rows are timed by E0 waits instead
        LDA $7E9F7D,X
        AND #$0040
        BNE eh_ret
        LDA #$00D1
        STA $7E9FFB
eh_ret: JML $878452         ; RTS: back to the text state machine
eh_ctl:
        JML $878423         ; a control code: the game's path

vwf_soft:                   ; carry clear when the pen is mid-line where the last letter left it and that wasn't a space
        PHB
        PEA $7F7F
        PLB
        PLB
        LDA $7E9FC5
        TAX
        LDA $7E9FD1,X
        CMP $F004
        BNE vs_skip
        LDA $7E9FD7,X
        CMP $F006
        BNE vs_skip
        TXA
        CMP $F008
        BNE vs_skip
        LDA $7E9FE3,X
        CMP $F00A
        BNE vs_skip
        LDA $F042           ; the last glyph (0: a space or a blank advance)
        BEQ vs_skip
        PLB
        CLC
        RTL
vs_skip:
        PLB
        SEC
        RTL

vwf_wrap:                   ; carry set when the word after the space at [$7E:9FF1:Y] won't fit; D = 0, DB = $7E
        PHB
        PEA $7F7F
        PLB
        PLB
        STY $F016           ; the script offset past the space
        LDA $7E9FC5
        TAX
        LDA $7E9FD1,X       ; px of the pen: as vwf_letter works it out
        CMP $F004
        BNE vw_fresh
        LDA $7E9FD7,X
        CMP $F006
        BNE vw_fresh
        TXA
        CMP $F008
        BNE vw_fresh
        LDA $7E9FE3,X
        CMP $F00A
        BNE vw_fresh
        LDA $F000
        BRA vw_have
vw_fresh:
        LDA $7E9FD1,X
        JSR col_px
        CLC
        ADC #$0007
        AND #$FFF8
        JSR line_margin
vw_have:
        STA $F018
        LDA ${WIDTHS:06X}   ; + the space (glyph 0)
        AND #$00FF
        CLC
        ADC $F018
        STA $F018           ; width of the line so far, including the space
        LDA $7E9FA1,X       ; the line's limit: columns * 12 px (8 px in a 16 px window)
        JSR col_px
        STA $F01A
        STZ $6C
        LDA $7E9FF1
        AND #$00FF
        STA $6E
        LDY $F016
vw_next:
        LDA [$6C],Y         ; DE <7E:addr>: a name printed from RAM is part of the word ("Melody's"): its letters count
        AND #$00FF
        CMP #$00DE
        BNE vw_letter
        INY
        LDA [$6C],Y
        STA $F01C           ; the name's address
        INY
        INY
        LDA [$6C],Y
        AND #$00FF
        CMP #$007E
        BEQ vw_ok1
        JMP vw_end
vw_ok1:
        INY
        PHY
        LDX $F01C
vw_nm:  LDA $7E0000,X       ; FC-terminated codes; NAME_MAP gives each one's letter (0: none)
        AND #$00FF
        CMP #$00FC
        BEQ vw_nmend
        PHX
        TAX
        LDA ${NAME_MAP:06X},X
        AND #$00FF
        BEQ vw_nmskip
        SEC
        SBC #$0020
        TAX
        LDA ${WIDTHS:06X},X
        AND #$00FF
        CLC
        ADC $F018
        STA $F018
vw_nmskip:
        PLX
        INX
        BRA vw_nm
vw_nmend:
        PLY
        JMP vw_next
vw_letter:
        LDA [$6C],Y         ; DF <24-bit>: the word goes on past the end of a detour (the next run's English, or a
        AND #$00FF          ; detour's jump back): measure on from there
        CMP #$00DF
        BNE vw_notdf
        INY
        LDA [$6C],Y
        STA $F01C
        INY
        INY
        LDA [$6C],Y
        AND #$00FF
        STA $6E
        LDY $F01C
        JMP vw_next
vw_notdf:
        LDA [$6C],Y         ; a letter is $01 xx: first byte 1, second the ASCII
        CMP #$0001          ; the soft space $0100 (dropped after a space): measure past it
        BNE vw_notsoft
        INY
        INY
        JMP vw_next
vw_notsoft:
        CMP #$2001
        BEQ vw_end          ; a space ends the word
        STA $F01C
        AND #$00FF
        CMP #$0001
        BNE vw_end          ; so does any other code
        LDA $F01C
        XBA
        AND #$00FF
        SEC
        SBC #$0020
        CMP #{FONT_COUNT}
        BCS vw_end
        TAX
        LDA ${WIDTHS:06X},X
        AND #$00FF
        CLC
        ADC $F018
        STA $F018
        INY
        INY
        JMP vw_next
vw_end: LDA $F018
        CMP $F01A
        BEQ vw_fits
        BCC vw_fits
        PLB
        SEC
        RTL
vw_fits:
        PLB
        CLC
        RTL

vwf_letter:                 ; A = $01xx; D = 0; DB = $7E
        PHB
        PEA $7F7F
        PLB
        PLB
        AND #$00FF
        STZ $F01C           ; a blank advance's width (0: a letter)
        CMP #$0020
        BCS vl_letter
        STA $F01C           ; $0101-$011F: a blank n px wide (the build's indent past a menu cursor)
        LDA #$0020
vl_letter:
        SEC
        SBC #$0020
        CMP #{FONT_COUNT}
        BCC vl_ok
        LDA #$0000
vl_ok:  STA $F014           ; glyph index
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #{FONT & 0xFFFF}
        STA $6C             ; [$6C] = the glyph's 16 rows ($6C-$6F: the text engine's scratch)
        LDA #{FONT >> 16}
        STA $6E
        LDX $F014
        LDA ${WIDTHS:06X},X
        AND #$00FF
        LDY $F01C
        BEQ vl_adv
        TYA
vl_adv: STA $F010           ; advance
        LDA $7E9FC5
        TAX
        LDA $7E9FD1,X       ; same window, line and place as the last letter left them?
        CMP $F004
        BNE vl_fresh
        LDA $7E9FD7,X
        CMP $F006
        BNE vl_fresh
        TXA
        CMP $F008
        BNE vl_fresh
        LDA $7E9FE3,X
        CMP $F00A
        BNE vl_fresh
        LDA $F000
        AND #$0007
        BNE vl_compose      ; yes, and a column is part-filled: draw on in it
        LDA $7E9FE3,X
        STA $F002
        BRA vl_clear
vl_fresh:
        LDA $7E9FD1,X       ; px = column * 12 (or 8), rounded up to a whole 8 px column
        JSR col_px
        CLC
        ADC #$0007
        AND #$FFF8
        JSR line_margin
        STA $F000
        LDA $7E9FE3,X
        STA $F002
vl_clear:
        LDA #$0000
        LDY #$001E
vl_clr: STA $F020,Y
        DEY
        DEY
        BPL vl_clr
vl_compose:                 ; buf[r] |= row >> shift, spill[r] = the bits pushed past the column
        LDA $F000
        AND #$0007
        STA $F00C
        LDY #$0000
vl_row: LDA [$6C],Y
        AND #$00FF
        XBA
        LDX $F00C
        BEQ vl_sh0
vl_sh:  LSR A
        DEX
        BNE vl_sh
vl_sh0: TYX
        SEP #$20
        STA $F030,X
        XBA
        ORA $F020,X
        STA $F020,X
        REP #$20
        INY
        CPY #$0010
        BNE vl_row
        LDA $F000
        LSR A
        LSR A
        LSR A
        STA $F012           ; the column within the line
        JSR vwf_column
        LDA $F000
        AND #$0007
        CLC
        ADC $F010
        STA $F00E
        LDA $F000
        CLC
        ADC $F010
        STA $F000
        LDA $F00E
        CMP #$0008
        BCC vl_done
        LDA $F002           ; the column is full: move to the next, its buffer is the spill
        CLC
        ADC #$0002
        JSR wrap_tile
        STA $F002
        LDX #$000E
vl_mv:  LDA $F030,X
        STA $F020,X
        STZ $F030,X
        DEX
        DEX
        BPL vl_mv
        LDA $F000
        AND #$0007
        BEQ vl_done
        LDA $F000
        LSR A
        LSR A
        LSR A
        STA $F012
        JSR vwf_column
vl_done:                    ; the game's tile cursor goes past a part-filled column too
        LDA $F000
        AND #$0007
        BEQ vl_t
        LDA $F002
        CLC
        ADC #$0002
        JSR wrap_tile
        BRA vl_t2
vl_t:   LDA $F002
vl_t2:  STA $F00A
        LDA $7E9FC5
        TAX
        LDA $F00A
        STA $7E9FE3,X
        LDA $F000           ; column = ceil(px / 12), or px / 8 rounded up in a 16 px window
        JSR px_col
        STA $7E9FD1,X
        STA $F004
        LDA $7E9FD7,X
        STA $F006
        TXA
        STA $F008
        LDA $F014
        STA $F042           ; the last glyph, for vwf_soft
        PLB
        RTL

line_margin:                ; A = the pen's px at a fresh line: px 0 of a 12 px window starts MARGIN px in, off the frame
        BNE lm_done
        LDA $7E9F7D,X
        AND #$0040
        BEQ lm_zero
        LDA #${MARGIN:04X}
        RTS
lm_zero:
        LDA #$0000
lm_done:
        RTS
col_px:                     ; A = a column count of window X -> px: * 12 in a 12 px window (bit $40), * 8 in a
        PHA                 ; 16 px one (whose column counts 8 px units)
        LDA $7E9F7D,X
        AND #$0040
        BEQ cp_8
        PLA
        ASL A
        ASL A
        STA $F01E
        ASL A
        CLC
        ADC $F01E
        RTS
cp_8:   PLA
        ASL A
        ASL A
        ASL A
        RTS

px_col:                     ; A = px -> the column count of window X, rounded up
        PHA
        LDA $7E9F7D,X
        AND #$0040
        BEQ pc_8
        PLA
        CLC
        ADC #$000B
        LDY #$0000
pc_div: CMP #$000C
        BCC pc_q
        SBC #$000C
        INY
        BRA pc_div
pc_q:   TYA
        RTS
pc_8:   PLA
        CLC
        ADC #$0007
        LSR A
        LSR A
        LSR A
        RTS

wrap_tile:                  ; A = the next tile; a 16 px window's tiles are a ring $9FB9-$9FBF (as $87:8843)
        PHX
        PHA
        LDA $7E9FC5
        TAX
        LDA $7E9F7D,X
        AND #$0040
        BNE wt_keep
        PLA
        CMP $7E9FBF,X
        BCC wt_out
        LDA $7E9FB9,X
        BRA wt_out
wt_keep:
        PLA
wt_out: PLX
        RTS

vwf_column:                 ; draw buf as tiles $F002, +1 at line column $F012; DB = $7F
        LDX #$000E
vc_cp:  LDA $F020,X
        STA $7EA09D,X
        DEX
        DEX
        BPL vc_cp
        PHB
        PEA $7E7E
        PLB
        PLB
        LDA $7FF002         ; VRAM word address = tile * 8 + $0ED6
        ASL A
        ASL A
        ASL A
        CLC
        ADC $0ED6
        STA $9F6B
        LDX $9FC5
        LDA $9F89,X         ; colours
        LDY #$0010          ; 16 rows of 1bpp at $A09D -> 2bpp at $A03D
        JSL call_98F1
        LDX $9FC5           ; a window with bit $80 stages its tiles at $7F:0000 + (tile - $9FB9) * 16
        LDA $9F7D,X
        BIT #$0080
        BEQ vc_dma
        LDA $7FF002
        SEC
        SBC $9FB9,X
        ASL A
        ASL A
        ASL A
        ASL A
        TAX
        LDY #$0000
vc_st:  LDA $A03D,Y
        STA $7F0000,X
        INX
        INX
        INY
        INY
        CPY #$0020
        BNE vc_st
        BRA vc_map
vc_dma:
        LDA $7FF040         ; the DMA runs at the next NMI, and a letter can draw two columns before it:
        INC A               ; give each column its own copy, a ring of 8 at $7F:F100
        AND #$0007
        STA $7FF040
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #$F100
        STA $6C
        STA $9F6D
        LDA #$007F
        STA $6E
        LDY #$001E
vc_rg:  LDA $A03D,Y
        STA [$6C],Y
        DEY
        DEY
        BPL vc_rg
        LDY #dma_desc & $FFFF
        LDA #dma_desc >> 16
        JSL call_8004
vc_map:
        LDX $9FC5           ; a column past a 12 px window's text width ((characters a line * 12 + 7) / 8
        LDA $9F7D,X         ; tiles) is drawn but not mapped: a space past the line's last letter put its tile on
        AND #$0040          ; the frame or beyond, where the box's clear never reaches and later letters show
        BEQ vc_mapok
        LDA $9FA1,X
        ASL A
        ASL A
        STA $6C
        ASL A
        CLC
        ADC $6C
        CLC
        ADC #$0007
        LSR A
        LSR A
        LSR A
        CMP $7FF012
        BEQ vc_skip
        BCC vc_skip
vc_mapok:
        LDX $9FC5           ; tilemap: row ($9F9B + $9FD7) * 64 + (x0 $9F95 + column) * 2
        LDA $9F9B,X
        CLC
        ADC $9FD7,X
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA $6C
        LDA $9F95,X
        CLC
        ADC $7FF012
        ASL A
        CLC
        ADC $6C
        TAY
        LDA $7FF002
        CLC
        ADC $9FAD,X
        STA $6C06,Y
        INC A
        STA $6C46,Y
        INC $0D30           ; tilemap changed
vc_skip:
        PLB
        RTS

call_98F1:
        PEA $8002
        JML $8798F1
call_8004:
        PEA $8002
        JML $878004
dma_desc:                   ; $8004 queue entry: handler, VRAM ($9F6B), source ($9F6D), bank, bytes
        .dw 5, $8A72, $FFFF, $FFFF, $007F, $0020
'''


WINDOW_SETUP_HOOK = 0x878EBD  # in $87:8EA0 (a window's descriptor copied): PEA $7E00 / PLB / PLB
WINDOW_SETUP_ORIGINAL = bytes.fromhex('F4007EABAB')
WINDOW_SETUP_CODE = '''
window_setup:               ; a window was (re)set up: the VWF's "same window, line and place" state no longer holds,
        LDA #$FFFF          ; or a new window in the old one's slot would draw on the old column's pixels
        STA $7FF008
        PEA $7E00
        PLB
        PLB
        RTL
'''


def apply(rom: bytearray) -> None:
    code, labels = assemble(CODE, SOURCE)
    put(rom, CODE, code)
    assert CODE + len(code) <= WIDTHS, f'VWF code runs into WIDTHS: ${CODE + len(code):06X}'
    o = snes_to_rom(WINDOW_SETUP_HOOK)
    if rom[o:o + 5] != WINDOW_SETUP_ORIGINAL:
        raise SystemExit(f'${WINDOW_SETUP_HOOK:06X} is not PEA $7E00 / PLB / PLB')
    wcode, wlabels = assemble(WINDOW_SETUP_CODE_AT, WINDOW_SETUP_CODE)
    put(rom, WINDOW_SETUP_CODE_AT, wcode)
    rom[o:o + 5] = bytes([0x22]) + wlabels['window_setup'].to_bytes(3, 'little') + b'\xEA'
    assert len(GRID_CODES) == len(GRID_LETTERS) == 70, (len(GRID_CODES), len(GRID_LETTERS))
    names, grid = bytearray(256), bytearray(512)
    for c, ch in zip(GRID_CODES, GRID_LETTERS):
        names[c] = ord(ch)
        grid[2 * c:2 * c + 2] = JP_GLYPH[ch].to_bytes(2, 'little')
    for i in range(10):
        names[0x5C + i] = ord('0') + i  # digits (the number buffer, and names): not grid codes
    put(rom, NAME_MAP, bytes(names))
    put(rom, GRID_MAP, bytes(grid))
    off = snes_to_rom(HOOK)
    if rom[off:off + 5] != HOOK_ORIGINAL:
        raise SystemExit(f'${HOOK:06X} is not the expected CMP #$00D0 / BCC')
    rom[off:off + 5] = bytes([0x5C]) + labels['en_hook'].to_bytes(3, 'little') + b'\xEA'
