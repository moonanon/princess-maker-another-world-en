#!/usr/bin/env python3
"""The game's script language and a recursive-descent walker over it (library; `dump_script.py` uses it).

The script is a byte stream read at `$7E:9FF1:$9FEF`: characters, and
control codes `$D0-$FC` (written as one byte, or `00xx` in two) followed by fixed-length arguments. The
codes jump, call, return and branch, so the stream is walked from its entry points, not read linearly.

    python3 -I tools/text/script_vm.py        # print the entry points and walk statistics
"""

import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rom'))
from RomExtract import rom as load_rom  # noqa: E402
from disasm import disassemble  # noqa: E402

TEXT_BANKS = (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC7, 0xC8)  # banks with `D8 DA` message starts and walkable script; C4/C6 are graphics
SCRIPT_END = 0x8000  # in every text bank the upper half is 65816 code (the JSLs into banks 80-88 are all there)
# The endings: C8:2462 `F5 7E:99C8` (the ending id) jumps to 3-byte entries in bank $84, the upper half of the
# graphics bank C4 (84:825B, 84:8937, ...): script there, at $8000 and up.
HIGH_SCRIPT_BANKS = (0x84,)


def in_script(bank: int, off: int) -> bool:
    """Whether (bank, off) can hold script: a text bank's lower half, or the upper half of a HIGH_SCRIPT_BANKS bank."""
    return bank in TEXT_BANKS and off < SCRIPT_END or bank in HIGH_SCRIPT_BANKS and off >= SCRIPT_END

# Argument bytes after each control code (handlers at $87:83DC + the table at $87:8382; each handler's
# reads of $9FEF counted). $DD is handled separately (3-byte native address + that routine's inline args),
# $DE/$DF/$F0-$F9 are flow codes.
ARGS = {
    0xD0: 0, 0xD1: 0, 0xD2: 0, 0xD3: 7, 0xD4: 1, 0xD5: 4, 0xD6: 4, 0xD7: 2, 0xD8: 0, 0xD9: 0, 0xDA: 0, 0xDB: 0,
    0xDC: 4, 0xE0: 2, 0xE1: 0, 0xE2: 3, 0xE3: 2, 0xE4: 1, 0xE5: 5, 0xE6: 5, 0xE7: 5, 0xE8: 5, 0xE9: 5,
    0xEA: 5, 0xEB: 3, 0xEC: 3, 0xED: 0, 0xEE: 3, 0xEF: 0, 0xFA: 4, 0xFB: 0,
}
TABLE_REFS: dict = {}  # (bank, off) a jump-table entry points at -> {(bank, entry offset, entry width)}, filled by walk()


def jump_targets(tokens: dict) -> set:
    """Every (bank, off) a walked DE/DF call or jump, or an F6-F9 branch, goes to. A run of text that one of them
    lands in the middle of is two runs: the jump starts the second."""
    out = set()
    for (bank, _off), (code, args, _nxt) in tokens.items():
        if code in (0xDE, 0xDF) and len(args) == 3:
            out.add((args[2], args[0] | args[1] << 8))
        elif code == 0xF6:
            out |= {(bank, args[0] | args[1] << 8), (bank, args[2] | args[3] << 8)}
        elif code == 0xF7:
            out |= {(args[2], args[0] | args[1] << 8), (args[5], args[3] | args[4] << 8)}
        elif code == 0xF8:
            out |= {(bank, args[3] | args[4] << 8), (bank, args[5] | args[6] << 8)}
        elif code == 0xF9:
            out |= {(args[5], args[3] | args[4] << 8), (args[8], args[6] | args[7] << 8)}
    return out | set(TABLE_REFS)


FIXED_JUMPS = {0xF6: 4, 0xF7: 6, 0xF8: 7, 0xF9: 9}  # code -> argument bytes (two or three targets inside)
# Native routines called by $DD that consume extra bytes after the call, counted from their disassembly.
SUBROUTINE_ARGS = {0x878A2F: 3, 0x888A2F: 3, 0x878D1A: 4, 0x8795B9: 3, 0x87984E: 0}
# Natives that set the script pointer from the ROM, read from their disassembly where the linear count can't
# tell: (inline argument bytes, falls through to the next token, script targets). Natives that pick a string
# from a bank $C7 string table are left out: those strings are dumped from `string_tables`.
NATIVE_JUMP_TABLE = 0x8897B2  # `DD 88:97B2 <24-bit pointer to v> <word table>`: goes to entry v-1, same bank

_rom = bytes(load_rom()) + bytes(64)


def _words(bank: int, off: int, n: int) -> list[int]:
    f = ((bank & 0x1F) << 16) | off
    return [_rom[f + 2 * i] | _rom[f + 2 * i + 1] << 8 for i in range(n)]


NATIVE_FLOW = {
    0x888723: (4, True, []),  # reads two words after the call and adds 4 to $9FEF
    0x87DD1F: (0, True, [(0xC7, 0x123C)]),  # every third call goes to C7:123C, otherwise carries on
    0x88E090: (0, False, [(0xC7, 0x6D3B), (0xC7, 0x6CE1)]),
    0x88AAED: (0, False, [(0xC8, w) for w in _words(0xC8, 0x0D64, 4)]),  # X from $88:AB25: 0, 2, 4 or 6
    # Builds `DF C8:<word>` at $7E:A633 from C8:6D9A (20 descending words; the first target ends the table).
    0x88C3B9: (0, False, [(0xC8, w) for w in _words(0xC8, 0x6D9A, 20)]),
}
# The word tables those natives read, (bank, offset) -> bytes: data laid between script blocks, never a block start.
DATA_TABLES = {(0xC8, 0x0D64): 8, (0xC8, 0x6D9A): 40}


def in_data_table(bank: int, off: int, length: int = 1) -> bool:
    """Whether bytes off..off+length-1 of `bank` touch one of DATA_TABLES."""
    return any(b == bank and off < o + n and o < off + length for (b, o), n in DATA_TABLES.items())

MAX_BAD_TABLE_ENTRIES = 2
MAX_TOKENS = 12000  # a walk longer than this has run into data
FILL_MAX_TOKENS = 800  # a block between two known ones is short


def file_offset(bank: int, off: int) -> int:
    return ((bank & 0x1F) << 16) | off


def entry_points() -> set[tuple[int, int]]:
    """(bank, offset) pairs the game code stores into $9FF1:$9FEF (`LDA #off; STA $7E9FEF; LDA #bank; STA $7E9FF1`)."""
    a = re.compile(rb'\xa9(..)\x8f\xef\x9f\x7e\xa9(.)\x00\x8f\xf1\x9f\x7e', re.S)
    b = re.compile(rb'\xa9(.)\x00\x8f\xf1\x9f\x7e\xa9(..)\x8f\xef\x9f\x7e', re.S)
    found = {(m.group(2)[0], int.from_bytes(m.group(1), 'little')) for m in a.finditer(_rom)}
    found |= {(m.group(1)[0], int.from_bytes(m.group(2), 'little')) for m in b.finditer(_rom)}
    return {e for e in found if e[0] in TEXT_BANKS}


# JSL entries that start a script through $87:8302 (Y = offset, A = bank; the first byte is the window).
WINDOW_ENTRIES = (0x8200, 0x820D, 0x8226, 0x8234)
WINDOWS = (0, 2, 4)
_WINDOW_JSL = rb'\x22(?:\x00\x82|\x0d\x82|\x26\x82|\x34\x82)\x87'


def _opens_script(bank: int, off: int) -> bool:
    """A window byte at `off` and a code the VM has a handler for after it."""
    f = file_offset(bank, off)
    hi = _rom[f + 1]
    code = (hi << 8) | _rom[f + 2] if hi < 8 else hi
    return _rom[f] in WINDOWS and not (0xFD <= code < 0x400 or code >= 0xB38)


def _offset_table(bank: int, table: int, stride: int, bank_from_table: bool, fixed_bank: int) -> list[tuple[int, int]]:
    """The script starts of an offset table, read entry by entry until one doesn't open a script (its length isn't in the code)."""
    out = []
    for i in range(128):
        f = file_offset(bank, table + stride * i)
        off = _rom[f] | _rom[f + 1] << 8
        b = _rom[f + 2] if bank_from_table else fixed_bank
        if b not in TEXT_BANKS or not _opens_script(b, off):
            break
        out.append((b, off + 1))
    return out


def window_entry_points() -> tuple[set[tuple[int, int]], list[list[tuple[int, int]]]]:
    """Script starts made through $87:8302: (fixed starts, offset tables), each start the byte after the window byte.

    Call shapes (disassembled at each kind of call site): `LDY #off; LDA #bank` or `LDA #off; TAY; LDA #bank`
    right before the JSL or a `BRA` to it; `LDA long,X; TAY` from a word table, with `LDA #bank` or a bank
    word beside each offset (`LDA long+2,X`); and `LDA long,X; STA $6C ... LDA [$6C],Y; TAY`, a table of
    sub-tables. Starts with a computed offset in some other way are missed.
    """
    fixed, tables = set(), []
    jsl = re.compile(_WINDOW_JSL)
    sites = [m.start() for m in jsl.finditer(_rom)]
    sites += [m.start() for m in re.finditer(rb'\x80(.)', _rom, re.S)
              if jsl.match(_rom, m.start() + 2 + m.group(1)[0]) and m.group(1)[0] < 0x80]
    for p in sites:
        pre = _rom[max(0, p - 24):p]
        g = (re.search(rb'\xa0(..)\xa9(.)\x00$', pre, re.S) or re.search(rb'\xa9(..)\xa8\xa9(.)\x00$', pre, re.S)
             or re.search(rb'\xa0(..)(?:\xa9..\x8f...)?\xa9(.)\x00$', pre, re.S))
        if g:
            bank, off = g.group(2)[0], int.from_bytes(g.group(1), 'little')
            if bank in TEXT_BANKS and _opens_script(bank, off):
                fixed.add((bank, off + 1))
            continue
        g = re.search(rb'\xbf(..)(.)\xa8(?:\xa9(.)\x00|\xbf(..).)$', pre, re.S)
        if g:
            table = int.from_bytes(g.group(1), 'little')
            if g.group(3):
                tables.append(_offset_table(g.group(2)[0], table, 2, False, g.group(3)[0]))
            elif int.from_bytes(g.group(4), 'little') == table + 2:
                tables.append(_offset_table(g.group(2)[0], table, 4, True, 0))
            continue
        g = re.search(rb'\xbf(..)(.)\x85\x6c\xa9(.)\x00\x85\x6e.*\xb7\x6c\xa8\xa9(.)\x00$', pre, re.S)
        if g:
            outer, sub_bank, bank = int.from_bytes(g.group(1), 'little'), g.group(3)[0], g.group(4)[0]
            for i in range(64):
                f = file_offset(g.group(2)[0], outer + 2 * i)
                sub = _offset_table(sub_bank, _rom[f] | _rom[f + 1] << 8, 2, False, bank)
                if not sub:
                    break
                tables.append(sub)
    return fixed, [t for t in tables if t]


_native: dict[int, tuple[int, bool]] = {}


def native_args(target: int) -> tuple[int, bool]:
    """(inline argument bytes, rewrites the script pointer) for a $DD native routine, from its disassembly.

    Linear to the first return: `INC $9FEF` is one byte, the known helpers add their own; a routine that
    stores to $9FEF replaces the script pointer, so the walk of that path ends.
    """
    if target not in _native:
        count, rewrites = 0, False
        for line in disassemble(_rom, target, 80, False, False):
            count += line.count('INC $9FEF')
            rewrites |= bool(re.search(r'STA \$(7E)?9FEF', line))
            m = re.search(r'(JSR|JSL) \$([0-9A-F]+)', line)
            if m:
                addr = int(m.group(2), 16)
                count += SUBROUTINE_ARGS.get(addr if m.group(1) == 'JSL' else (target & 0xFF0000) | addr, 0)
            if re.search(r'\b(RTL|RTS|JMP|JML)\b', line):
                break
        _native[target] = (count, rewrites)
    return _native[target]


def walk(starts, past_fc: bool = False, known: dict | None = None, follow_tables: bool = True, max_tokens: int = MAX_TOKENS, trace: dict | None = None) -> tuple[dict, list]:
    """Walk the script from `starts`: {(bank, off): (code, arg bytes, next off)} and a list of problems.

    A problem ('invalid', ...) means the walk read a code the VM has no handler for: the entry point was
    not really script. A run that reads one is dropped whole; a bad jump-table entry (`softinvalid`) only loses its own run, since table lengths are guessed.

    `$FC` returns when a `$DE` call is pending, but with nothing pending it only yields to the game code
    and the message carries on after it; which it is can't be told
    statically, so `past_fc` makes the walk continue after it (see `walk_entry_points`).

    `trace`, when given, is filled with {run start: the token that jumped there}, to find where a walk went wrong.
    """
    seen: dict = {}
    known = {} if known is None else known  # tokens walked by earlier calls: not walked again
    warn: list = []
    todo = [(b, o, False) for b, o in starts]  # (bank, offset, soft)
    queued = set(starts)  # every jump target seen so far: each one is the start of a block
    while todo:
        bank, off, soft = todo.pop()
        if len(seen) > max_tokens:
            warn.append(('invalid', bank, off, -2))  # a real message chain is far shorter: this is data
            break
        if bank not in TEXT_BANKS and bank not in HIGH_SCRIPT_BANKS:
            warn.append(('badtarget', bank, off))
            continue
        run: dict = {}
        run_todo: list = []
        ok = True

        def table(start: int, lead: int, width: int) -> tuple[list, int]:
            """A jump table at `start`: `lead` bytes, then `width`-byte entries. The length is not in the stream;
            the table ends at its first forward target, or where a block another jump goes to starts (tables
            are packed back to back: C8 `$3F28`, six entries, then the next block's code). The next block isn't
            always a known target yet, so a `DD` call to a bank 87/88 native also ends it (C8 `$4CB1`), and so
            does an entry that points into the code half of a bank (C8 `$4CD5`, four entries, then text)."""
            p, end, entries = start + lead, 1 << 30, []
            while p < end and len(entries) < 64 and not (entries and ((bank, p) in queued or (bank, p) in known)):
                g = file_offset(bank, p)
                if entries and _rom[g] == 0xDD and _rom[g + 3] in (0x87, 0x88):
                    break
                target_bank = _rom[g + 2] if width == 3 else bank
                target = _rom[g] | _rom[g + 1] << 8
                if entries and not in_script(target_bank, target):
                    break
                entries.append((target_bank, target))
                TABLE_REFS.setdefault((target_bank, target), set()).add((bank, p, width))
                if target_bank == bank and target > p:
                    end = min(end, target)
                p += width
            return entries, p

        while (bank, off) not in seen and (bank, off) not in known and (bank, off) not in run:
            f = file_offset(bank, off)
            hi = _rom[f]
            code, size = ((hi << 8) | _rom[f + 1], 2) if hi < 8 else (hi, 1)
            pos = off + size
            if 0xFD <= code < 0x400 or code >= 0xB38 or not in_script(bank, off):
                warn.append(('softinvalid' if soft else 'invalid', bank, off, code))
                ok = False
                break
            if code < 0xD0 or code >= 0x400:
                run[(bank, off)] = (code, b'', pos)
                off = pos
                continue
            byte = lambda k: _rom[file_offset(bank, pos + k)]  # noqa: E731
            word = lambda k: byte(k) | byte(k + 1) << 8  # noqa: E731
            if code == 0xDD:
                target = int.from_bytes(_rom[f + size:f + size + 3], 'little')
                if target == NATIVE_JUMP_TABLE:
                    if byte(5) != 0x7E:  # the value it indexes by is always in RAM (33 of 33 walked calls)
                        warn.append(('softinvalid' if soft else 'invalid', bank, off, code))
                        ok = False
                        break
                    entries, p = table(pos + 3, 3, 2)
                    run[(bank, off)] = (code, _rom[f + size:f + size + 6], p)
                    run_todo += [(b, o, True) for b, o in entries]
                    break
                if target in NATIVE_FLOW:
                    extra, falls_through, targets = NATIVE_FLOW[target]
                    rewrites = not falls_through
                    run_todo += [(b, o, False) for b, o in targets]
                else:
                    try:
                        extra, rewrites = native_args(target)
                    except ValueError:
                        warn.append(('softinvalid' if soft else 'invalid', bank, off, code))
                        ok = False
                        break
                run[(bank, off)] = (code, _rom[f + size:f + size + 3 + extra], pos + 3 + extra)
                off = pos + 3 + extra
                if rewrites:
                    break
                continue
            if code in ARGS:
                n = ARGS[code]
                run[(bank, off)] = (code, _rom[f + size:f + size + n], pos + n)
                off = pos + n
                continue
            if code in (0xDE, 0xDF):  # call / jump to a 24-bit script address
                run[(bank, off)] = (code, _rom[f + size:f + size + 3], pos + 3)
                run_todo.append((byte(2), word(0), False))
                if code == 0xDE:
                    off = pos + 3
                    continue
                break
            if code == 0xFC:  # return (or yield to the game code when nothing was called)
                # A yield is followed by a mode byte (00, 02 or 04) in front of the next control code.
                arg = 1 if byte(0) in (0, 2, 4) and 0xD0 <= byte(1) <= 0xFC else 0
                run[(bank, off)] = (code, _rom[f + size:f + size + arg], pos + arg)
                if past_fc:
                    off = pos + arg
                    continue
                break
            if code in FIXED_JUMPS:
                n = FIXED_JUMPS[code]
                run[(bank, off)] = (code, _rom[f + size:f + size + n], pos + n)
                if code == 0xF6:
                    run_todo += [(bank, word(0), False), (bank, word(2), False)]
                elif code == 0xF7:
                    run_todo += [(byte(2), word(0), False), (byte(5), word(3), False)]
                elif code == 0xF8:
                    run_todo += [(bank, word(3), False), (bank, word(5), False)]
                else:
                    run_todo += [(byte(5), word(3), False), (byte(8), word(6), False)]
                break
            # $F0-$F5: jump tables indexed by the last menu choice ($7E:A031).
            lead = 0 if code < 0xF2 else 3
            if lead and byte(2) != 0x7E:  # $F2-$F5 index by a RAM value: every walked one points into bank $7E
                warn.append(('softinvalid' if soft else 'invalid', bank, off, code))
                ok = False
                break
            entries, p = table(pos, lead, 2 if code in (0xF0, 0xF2, 0xF4) else 3)
            run[(bank, off)] = (code, _rom[f + size:f + size + lead], p)
            run_todo += [(b, o, True) for b, o in entries]
            break
        if ok and any(t[0] not in TEXT_BANKS + HIGH_SCRIPT_BANKS and t[0] != 0x7E for t in run_todo if not t[2]):
            warn.append(('softinvalid' if soft else 'invalid', bank, off, -1))  # jumps out of the script banks: not script
            ok = False
        if ok:
            seen.update(run)
            todo += [(b, o, sf or soft) for b, o, sf in run_todo if follow_tables or not sf]
            queued.update((b, o) for b, o, _ in run_todo)
            if trace is not None:
                last = max(run, default=(bank, off))
                for b, o, _ in run_todo:
                    trace.setdefault((b, o), last)
    return seen, warn


def string_tables(bank: int = 0xC7, lo: int = 0x400, hi: int = 0x1250) -> list[tuple[int, list[int]]]:
    """Pointer tables of FC-terminated strings in the data area of a text bank: [(table offset, [string offsets])].

    A table is a run of at least four ascending little-endian words that all point back into `lo..hi`;
    the scan finds 17 of them in bank $C7 (names, items, menu words), covering $C7:041A-$1090.
    """
    base = file_offset(bank, 0)
    word = lambda o: _rom[base + o] | _rom[base + o + 1] << 8  # noqa: E731
    tables, o = [], lo
    while o < hi:
        n, prev = 0, 0
        while o + 2 * n < hi and lo <= word(o + 2 * n) < hi and word(o + 2 * n) >= prev:
            prev = word(o + 2 * n)
            n += 1
        if n >= 4:
            tables.append((o, [word(o + 2 * i) for i in range(n)]))
            o += 2 * n
        else:
            o += 1
    return tables


# The data areas that hold pointer tables of FC-terminated strings (found by `string_tables`'s scan).
STRING_TABLE_AREAS = (
    (0xC7, 0x400, 0x1250),  # 17 tables: weapon/item names, menu words ($C7:041A-$1090)
    (0xC8, 0x1EE3, 0x23EB),  # 10 tables of 11-12 names each (ending titles)
)


def all_string_tables() -> list[tuple[int, int, list[int]]]:
    """[(bank, table offset, [string offsets])] over every `STRING_TABLE_AREAS` entry."""
    return [(bank, table, offsets) for bank, lo, hi in STRING_TABLE_AREAS for table, offsets in string_tables(bank, lo, hi)]


def read_string(bank: int, off: int) -> tuple[list[int], int]:
    """The character codes of the string at `off` up to its `$FC`, and the offset after it (control codes skipped by length)."""
    codes = []
    while True:
        f = file_offset(bank, off)
        hi = _rom[f]
        code, size = ((hi << 8) | _rom[f + 1], 2) if hi < 8 else (hi, 1)
        off += size
        if code == 0xFC:
            return codes, off
        if code in ARGS:
            off += ARGS[code]
        codes.append(code)
        if len(codes) > 200:
            return codes, off


def message_starts() -> set[tuple[int, int]]:
    """Every `D8 DA` / `FC DA` (either code may be written in two bytes, `00D8`) in the text banks: a message opens with `DA`."""
    found = set()
    for bank in TEXT_BANKS:
        base = file_offset(bank, 0)
        for m in re.finditer(rb'(?:\x00?[\xd8\xfc])(\x00?\xda)', _rom[base:base + 0x10000], re.S):
            found.add((bank, m.start(1)))
    return found




ENDS = {0xDF, 0xFC, 0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9}
OPENERS = set(range(0xD1, 0xFD))


def start_is_weak(start: tuple[int, int]) -> bool:
    """True when the byte after a terminator doesn't open the way a message does (a control that sets one up)."""
    f = file_offset(*start)
    hi = _rom[f]
    code = ((hi << 8) | _rom[f + 1]) if hi < 8 else hi
    return (code & 0xFF if 0x100 <= code < 0x400 else code) not in OPENERS


def clean(warn: list, strict: bool = False) -> bool:
    """A walk is script when it read no invalid code and at most a couple of its guessed table entries were bad (none when `strict`)."""
    bad_table = sum(w[0] == 'softinvalid' for w in warn)
    return not any(w[0] == 'invalid' for w in warn) and bad_table <= (0 if strict else MAX_BAD_TABLE_ENTRIES)


def walk_entry_points() -> tuple[list, dict]:
    """Walk each entry point and message start alone and keep those that stay valid.

    Returns (good starts, merged tokens). Pass 1 stops at `$FC`. Pass 2 retries from the byte after every
    `$FC` seen, continuing past further ones, and keeps one only if it never reads an invalid code outside a guessed jump-table entry.
    """
    good, merged = [], {}
    fixed, tables = window_entry_points()
    for entry in sorted(entry_points() | message_starts() | fixed):
        seen, warn = walk([entry], known=merged)
        if (entry in seen or entry in merged) and clean(warn):
            good.append(entry)
            merged.update(seen)
    for table in tables:  # a table's length is guessed: it ends at its first entry that isn't script
        for entry in table:
            seen, warn = walk([entry], known=merged)
            if not ((entry in seen or entry in merged) and clean(warn)):
                break
            good.append(entry)
            merged.update(seen)
    # Blocks are laid end to end: whatever follows a token that ends a run (return, goto, a jump, a table)
    # is another block that nothing in the walked code points at. Take it if it walks clean and opens like one.
    tried = set()
    while True:
        fresh = [(b, n) for (b, o), (c, a, n) in merged.items()
                 if (c in ENDS or (c == 0xDD and native_args(int.from_bytes(a[:3], 'little'))[1])) and b in TEXT_BANKS + HIGH_SCRIPT_BANKS and (b, n) not in merged and (b, n) not in tried and not in_data_table(b, n)]
        if not fresh:
            break
        for start in fresh:
            tried.add(start)
            seen, warn = walk([start], past_fc=True, known=merged, follow_tables=False, max_tokens=FILL_MAX_TOKENS)
            if start in seen and clean(warn, strict=start_is_weak(start)):
                merged.update(seen)
    return good, merged


if __name__ == '__main__':
    points = entry_points()
    good, tokens = walk_entry_points()
    print(f'{len(points)} entry points, {len(good)} valid, {len(tokens)} tokens')
    print(collections.Counter(f'{b:02X}' for b, _ in tokens))
