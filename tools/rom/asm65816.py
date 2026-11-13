"""A small two-pass 65816 assembler for patch modules: enough for hooks and short routines, no macros.

    from asm65816 import assemble
    code, labels = assemble(0xDB0000, '''
        vwf:    LDA #$1234      ; immediates sized by the tracked REP/SEP state (starts M16 X16)
                STA $7FF000,X   ; $xx = direct page, $xxxx = absolute, $xxxxxx = long
                BNE vwf         ; labels; operands may be expressions (label+2, font>>16, $8002)
                RTL
        table:  .dw 5, $8A72    ; .db / .dw / .dl data
    ''')

A label operand (or any expression containing one) takes the long form where the instruction has one
(LDA/STA/ADC/SBC/AND/ORA/EOR/CMP with no index or ,X), the absolute form otherwise; JSL/JML are long,
JSR/JMP/PEA absolute (low 16 bits), branches relative (BRL is 16-bit). Write `.m8`/`.m16`/`.x8`/`.x16`
to set the flag state where REP/SEP tracking can't know it (the start of a routine entered from elsewhere).
"""

import re

# mnemonic -> {mode: opcode}. Modes: imp acc imm dp dpx abs absx absy long longx dpiy dpily rel rell
OPS = {
    'ADC': {'imm': 0x69, 'dp': 0x65, 'dpx': 0x75, 'abs': 0x6D, 'absx': 0x7D, 'absy': 0x79, 'long': 0x6F, 'longx': 0x7F, 'dpily': 0x77},
    'AND': {'imm': 0x29, 'dp': 0x25, 'dpx': 0x35, 'abs': 0x2D, 'absx': 0x3D, 'absy': 0x39, 'long': 0x2F, 'longx': 0x3F, 'dpily': 0x37},
    'CMP': {'imm': 0xC9, 'dp': 0xC5, 'dpx': 0xD5, 'abs': 0xCD, 'absx': 0xDD, 'absy': 0xD9, 'long': 0xCF, 'longx': 0xDF, 'dpily': 0xD7},
    'EOR': {'imm': 0x49, 'dp': 0x45, 'dpx': 0x55, 'abs': 0x4D, 'absx': 0x5D, 'absy': 0x59, 'long': 0x4F, 'longx': 0x5F, 'dpily': 0x57},
    'LDA': {'imm': 0xA9, 'dp': 0xA5, 'dpx': 0xB5, 'abs': 0xAD, 'absx': 0xBD, 'absy': 0xB9, 'long': 0xAF, 'longx': 0xBF, 'dpily': 0xB7},
    'ORA': {'imm': 0x09, 'dp': 0x05, 'dpx': 0x15, 'abs': 0x0D, 'absx': 0x1D, 'absy': 0x19, 'long': 0x0F, 'longx': 0x1F, 'dpily': 0x17},
    'SBC': {'imm': 0xE9, 'dp': 0xE5, 'dpx': 0xF5, 'abs': 0xED, 'absx': 0xFD, 'absy': 0xF9, 'long': 0xEF, 'longx': 0xFF, 'dpily': 0xF7},
    'STA': {'dp': 0x85, 'dpx': 0x95, 'abs': 0x8D, 'absx': 0x9D, 'absy': 0x99, 'long': 0x8F, 'longx': 0x9F, 'dpily': 0x97},
    'LDX': {'imm': 0xA2, 'dp': 0xA6, 'abs': 0xAE, 'absy': 0xBE},
    'LDY': {'imm': 0xA0, 'dp': 0xA4, 'dpx': 0xB4, 'abs': 0xAC, 'absx': 0xBC},
    'STX': {'dp': 0x86, 'abs': 0x8E},
    'STY': {'dp': 0x84, 'abs': 0x8C},
    'STZ': {'dp': 0x64, 'dpx': 0x74, 'abs': 0x9C, 'absx': 0x9E},
    'CPX': {'imm': 0xE0, 'dp': 0xE4, 'abs': 0xEC},
    'CPY': {'imm': 0xC0, 'dp': 0xC4, 'abs': 0xCC},
    'BIT': {'imm': 0x89, 'dp': 0x24, 'abs': 0x2C, 'absx': 0x3C},
    'INC': {'acc': 0x1A, 'dp': 0xE6, 'abs': 0xEE, 'absx': 0xFE},
    'DEC': {'acc': 0x3A, 'dp': 0xC6, 'abs': 0xCE, 'absx': 0xDE},
    'ASL': {'acc': 0x0A, 'dp': 0x06, 'abs': 0x0E},
    'LSR': {'acc': 0x4A, 'dp': 0x46, 'abs': 0x4E},
    'ROL': {'acc': 0x2A, 'dp': 0x26, 'abs': 0x2E},
    'ROR': {'acc': 0x6A, 'dp': 0x66, 'abs': 0x6E},
    'JSR': {'abs': 0x20},
    'JMP': {'abs': 0x4C},
    'JSL': {'long': 0x22},
    'JML': {'long': 0x5C},
    'PEA': {'abs': 0xF4},
    'REP': {'imm8': 0xC2},
    'SEP': {'imm8': 0xE2},
}
IMPLIED = {
    'CLC': 0x18, 'SEC': 0x38, 'CLI': 0x58, 'SEI': 0x78, 'CLV': 0xB8, 'NOP': 0xEA, 'XBA': 0xEB,
    'INX': 0xE8, 'INY': 0xC8, 'DEX': 0xCA, 'DEY': 0x88, 'TAX': 0xAA, 'TAY': 0xA8, 'TXA': 0x8A, 'TYA': 0x98,
    'TXY': 0x9B, 'TYX': 0xBB, 'TCD': 0x5B, 'TDC': 0x7B, 'TCS': 0x1B, 'TSC': 0x3B, 'TXS': 0x9A, 'TSX': 0xBA,
    'PHA': 0x48, 'PLA': 0x68, 'PHX': 0xDA, 'PLX': 0xFA, 'PHY': 0x5A, 'PLY': 0x7A, 'PHB': 0x8B, 'PLB': 0xAB,
    'PHD': 0x0B, 'PLD': 0x2B, 'PHK': 0x4B, 'PHP': 0x08, 'PLP': 0x28, 'RTS': 0x60, 'RTL': 0x6B, 'RTI': 0x40,
}
BRANCH = {'BCC': 0x90, 'BCS': 0xB0, 'BEQ': 0xF0, 'BNE': 0xD0, 'BMI': 0x30, 'BPL': 0x10, 'BVC': 0x50,
          'BVS': 0x70, 'BRA': 0x80}
SIZE = {'imp': 1, 'acc': 1, 'imm8': 2, 'dp': 2, 'dpx': 2, 'dpiy': 2, 'dpily': 2, 'abs': 3, 'absx': 3,
        'absy': 3, 'long': 4, 'longx': 4, 'rel': 2, 'rell': 3}
MEM_IMM = {'ADC', 'AND', 'CMP', 'EOR', 'LDA', 'ORA', 'SBC', 'BIT'}  # immediate sized by M
IDX_IMM = {'LDX', 'LDY', 'CPX', 'CPY'}  # immediate sized by X


class AsmError(Exception):
    pass


def _eval(expr: str, labels: dict[str, int] | None) -> int:
    if labels is None:  # first pass: sizes come from the operand's syntax, not its value
        return 0
    py = re.sub(r'\$([0-9A-Fa-f]+)', r'0x\1', expr)
    try:
        return int(eval(py, {'__builtins__': {}}, labels))  # noqa: S307 - our own patch source
    except NameError as e:
        raise AsmError(f'unknown label in {expr!r}: {e}') from None


def _has_label(expr: str) -> bool:
    return bool(re.search(r'(?<![$\w])[A-Za-z_]\w*', re.sub(r'\$[0-9A-Fa-f]+', '', expr)))


def _mode(mn: str, opnd: str) -> tuple[str, str]:
    """(mode, expression) from the operand's syntax."""
    if opnd == '':
        return ('acc' if mn in OPS and 'acc' in OPS[mn] else 'imp'), ''
    if opnd.upper() == 'A':
        return 'acc', ''
    if opnd.startswith('#'):
        return 'imm', opnd[1:]
    m = re.fullmatch(r'\[(.+)\],\s*[Yy]', opnd)
    if m:
        return 'dpily', m.group(1)
    m = re.fullmatch(r'\((.+)\),\s*[Yy]', opnd)
    if m:
        return 'dpiy', m.group(1)
    idx = ''
    m = re.fullmatch(r'(.+?),\s*([XxYy])', opnd)
    if m:
        opnd, idx = m.group(1), m.group(2).lower()
    if _has_label(opnd):
        ops = OPS[mn]
        size = 'long' if (('long' + idx) in ops and idx != 'y') else 'abs'
    else:
        h = re.fullmatch(r'\$([0-9A-Fa-f]+)', opnd.strip())
        n = len(h.group(1)) if h else 4
        size = 'dp' if n <= 2 else 'abs' if n <= 4 else 'long'
    return size + idx, opnd


def assemble(org: int, source: str) -> tuple[bytes, dict[str, int]]:
    """Assemble `source` at SNES address `org`; returns the bytes and the label addresses."""
    lines = []
    for raw in source.splitlines():
        line = raw.split(';', 1)[0].strip()
        while True:
            m = re.match(r'([A-Za-z_]\w*):\s*(.*)', line)
            if not m:
                break
            lines.append(('label', m.group(1)))
            line = m.group(2)
        if line:
            lines.append(('op', line))

    def run(labels: dict[str, int] | None) -> tuple[bytearray, dict[str, int]]:
        out = bytearray()
        found: dict[str, int] = {}
        m16 = x16 = True
        for kind, text in lines:
            pc = org + len(out)
            if kind == 'label':
                found[text] = pc
                continue
            mn, _, opnd = text.partition(' ')
            mn, opnd = mn.upper(), opnd.strip()
            if mn in ('.M8', '.M16', '.X8', '.X16'):
                if mn[1] == 'M':
                    m16 = mn == '.M16'
                else:
                    x16 = mn == '.X16'
                continue
            if mn in ('.DB', '.DW', '.DL'):
                width = {'.DB': 1, '.DW': 2, '.DL': 3}[mn]
                for part in [p.strip() for p in opnd.split(',') if p.strip()]:
                    v = _eval(part, labels)
                    out += (v & ((1 << (8 * width)) - 1)).to_bytes(width, 'little')
                continue
            if mn in IMPLIED and opnd == '':
                out.append(IMPLIED[mn])
                continue
            if mn in BRANCH or mn == 'BRL':
                target = _eval(opnd, labels)
                if mn == 'BRL':
                    off = target - (pc + 3)
                    if labels is not None and not -0x8000 <= off < 0x8000:
                        raise AsmError(f'{text}: out of range')
                    out += bytes([0x82]) + (off & 0xFFFF).to_bytes(2, 'little')
                else:
                    off = target - (pc + 2)
                    if labels is not None and not -128 <= off < 128:
                        raise AsmError(f'{text}: branch out of range ({off})')
                    out += bytes([BRANCH[mn], off & 0xFF])
                continue
            if mn not in OPS:
                raise AsmError(f'unknown instruction: {text}')
            mode, expr = _mode(mn, opnd)
            ops = OPS[mn]
            if mn in ('REP', 'SEP'):
                v = _eval(expr, labels)
                out += bytes([ops['imm8'], v])
                if v & 0x20:
                    m16 = mn == 'REP'
                if v & 0x10:
                    x16 = mn == 'REP'
                continue
            if mode == 'imm':
                wide = m16 if mn in MEM_IMM else x16 if mn in IDX_IMM else False
                v = _eval(expr, labels)
                out += bytes([ops['imm']]) + (v & (0xFFFF if wide else 0xFF)).to_bytes(2 if wide else 1, 'little')
                continue
            if mode not in ops:
                raise AsmError(f'{text}: no {mode} form for {mn}')
            v = _eval(expr, labels) if expr else 0
            n = SIZE[mode] - 1
            out.append(ops[mode])
            if n:
                out += (v & ((1 << (8 * n)) - 1)).to_bytes(n, 'little')
        return out, found

    first, labels = run(None)
    code, labels2 = run(labels)
    if len(code) != len(first) or labels2 != labels:
        raise AsmError('label-dependent sizes changed between passes')
    return bytes(code), labels
