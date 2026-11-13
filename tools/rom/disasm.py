#!/usr/bin/env python3
"""Disassemble 65816 code straight from the base ROM (there is no disassembly for this game).

    python3 -I tools/rom/disasm.py <snes address> [count] [--m8] [--x8]

The address is a HiROM SNES address (`C0B11F` or `$C0:B11F`). It follows REP/SEP for the
accumulator and index widths, starting 16-bit unless --m8/--x8 say otherwise; a wrong start shows
up as nonsense right away. It doesn't follow branches: it reads straight on for `count` lines (40).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from RomExtract import rom as load_rom, snes_to_rom  # noqa: E402

# Addressing modes: the operand's size (m/x: by the flag) and how to print it.
MODES = {
    'imp': (0, '{}'),
    'acc': (0, 'A'),
    'imm8': (1, '#${:02X}'),
    'immm': ('m', '#${}'),
    'immx': ('x', '#${}'),
    'dp': (1, '${:02X}'),
    'dpx': (1, '${:02X},X'),
    'dpy': (1, '${:02X},Y'),
    'idp': (1, '(${:02X})'),
    'idpx': (1, '(${:02X},X)'),
    'idpy': (1, '(${:02X}),Y'),
    'ildp': (1, '[${:02X}]'),
    'ildpy': (1, '[${:02X}],Y'),
    'sr': (1, '${:02X},S'),
    'sry': (1, '(${:02X},S),Y'),
    'abs': (2, '${:04X}'),
    'absx': (2, '${:04X},X'),
    'absy': (2, '${:04X},Y'),
    'iabs': (2, '(${:04X})'),
    'iabsx': (2, '(${:04X},X)'),
    'ilabs': (2, '[${:04X}]'),
    'long': (3, '${:06X}'),
    'longx': (3, '${:06X},X'),
    'rel': (1, 'rel'),
    'rell': (2, 'rell'),
    'bm': (2, 'bm'),
}

# One row per high nibble: (mnemonic, mode) for opcodes x0..xF.
_ROWS = """
BRK imm8|ORA idpx|COP imm8|ORA sr|TSB dp|ORA dp|ASL dp|ORA ildp|PHP imp|ORA immm|ASL acc|PHD imp|TSB abs|ORA abs|ASL abs|ORA long
BPL rel|ORA idpy|ORA idp|ORA sry|TRB dp|ORA dpx|ASL dpx|ORA ildpy|CLC imp|ORA absy|INC acc|TCS imp|TRB abs|ORA absx|ASL absx|ORA longx
JSR abs|AND idpx|JSL long|AND sr|BIT dp|AND dp|ROL dp|AND ildp|PLP imp|AND immm|ROL acc|PLD imp|BIT abs|AND abs|ROL abs|AND long
BMI rel|AND idpy|AND idp|AND sry|BIT dpx|AND dpx|ROL dpx|AND ildpy|SEC imp|AND absy|DEC acc|TSC imp|BIT absx|AND absx|ROL absx|AND longx
RTI imp|EOR idpx|WDM imm8|EOR sr|MVP bm|EOR dp|LSR dp|EOR ildp|PHA imp|EOR immm|LSR acc|PHK imp|JMP abs|EOR abs|LSR abs|EOR long
BVC rel|EOR idpy|EOR idp|EOR sry|MVN bm|EOR dpx|LSR dpx|EOR ildpy|CLI imp|EOR absy|PHY imp|TCD imp|JML long|EOR absx|LSR absx|EOR longx
RTS imp|ADC idpx|PER rell|ADC sr|STZ dp|ADC dp|ROR dp|ADC ildp|PLA imp|ADC immm|ROR acc|RTL imp|JMP iabs|ADC abs|ROR abs|ADC long
BVS rel|ADC idpy|ADC idp|ADC sry|STZ dpx|ADC dpx|ROR dpx|ADC ildpy|SEI imp|ADC absy|PLY imp|TDC imp|JMP iabsx|ADC absx|ROR absx|ADC longx
BRA rel|STA idpx|BRL rell|STA sr|STY dp|STA dp|STX dp|STA ildp|DEY imp|BIT immm|TXA imp|PHB imp|STY abs|STA abs|STX abs|STA long
BCC rel|STA idpy|STA idp|STA sry|STY dpx|STA dpx|STX dpy|STA ildpy|TYA imp|STA absy|TXS imp|TXY imp|STZ abs|STA absx|STZ absx|STA longx
LDY immx|LDA idpx|LDX immx|LDA sr|LDY dp|LDA dp|LDX dp|LDA ildp|TAY imp|LDA immm|TAX imp|PLB imp|LDY abs|LDA abs|LDX abs|LDA long
BCS rel|LDA idpy|LDA idp|LDA sry|LDY dpx|LDA dpx|LDX dpy|LDA ildpy|CLV imp|LDA absy|TSX imp|TYX imp|LDY absx|LDA absx|LDX absy|LDA longx
CPY immx|CMP idpx|REP imm8|CMP sr|CPY dp|CMP dp|DEC dp|CMP ildp|INY imp|CMP immm|DEX imp|WAI imp|CPY abs|CMP abs|DEC abs|CMP long
BNE rel|CMP idpy|CMP idp|CMP sry|PEI dp|CMP dpx|DEC dpx|CMP ildpy|CLD imp|CMP absy|PHX imp|STP imp|JML ilabs|CMP absx|DEC absx|CMP longx
CPX immx|SBC idpx|SEP imm8|SBC sr|CPX dp|SBC dp|INC dp|SBC ildp|INX imp|SBC immm|NOP imp|XBA imp|CPX abs|SBC abs|INC abs|SBC long
BEQ rel|SBC idpy|SBC idp|SBC sry|PEA abs|SBC dpx|INC dpx|SBC ildpy|SED imp|SBC absy|PLX imp|XCE imp|JSR iabsx|SBC absx|INC absx|SBC longx
"""
OPCODES = [tuple(cell.split()) for row in _ROWS.strip().splitlines() for cell in row.split('|')]
assert len(OPCODES) == 256


def disassemble(rom: bytes, address: int, count: int, m8: bool, x8: bool) -> list[str]:
    lines = []
    for _ in range(count):
        at = snes_to_rom(address)
        op = rom[at]
        name, mode = OPCODES[op]
        size, fmt = MODES[mode]
        if size == 'm':
            size = 1 if m8 else 2
        elif size == 'x':
            size = 1 if x8 else 2
        raw = rom[at + 1 : at + 1 + size]
        value = int.from_bytes(raw, 'little')
        if mode == 'rel':
            target = (address & 0xFF0000) | ((address + 2 + (value - 256 if value > 127 else value)) & 0xFFFF)
            operand = f'${target:06X}'
        elif mode == 'rell':
            target = (address & 0xFF0000) | ((address + 3 + (value - 65536 if value > 32767 else value)) & 0xFFFF)
            operand = f'${target:06X}'
        elif mode == 'bm':
            operand = f'${raw[1]:02X},${raw[0]:02X}'
        elif mode in ('immm', 'immx'):
            operand = f'#${value:0{size * 2}X}'
        elif mode in ('imp', 'acc'):
            operand = '' if mode == 'imp' else 'A'
        else:
            operand = fmt.format(value)
        if name == 'REP':
            m8 = m8 and not value & 0x20
            x8 = x8 and not value & 0x10
        elif name == 'SEP':
            m8 = m8 or bool(value & 0x20)
            x8 = x8 or bool(value & 0x10)
        hexbytes = ' '.join(f'{b:02X}' for b in rom[at : at + 1 + size])
        lines.append(f'{address:06X}  {hexbytes:<12} {name} {operand}'.rstrip())
        address = (address & 0xFF0000) | ((address + 1 + size) & 0xFFFF)
    return lines


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        sys.exit(__doc__)
    address = int(args[0].replace('$', '').replace(':', ''), 16)
    count = int(args[1]) if len(args) > 1 else 40
    rom = load_rom()
    print('\n'.join(disassemble(rom, address, count, '--m8' in sys.argv, '--x8' in sys.argv)))


if __name__ == '__main__':
    main()
