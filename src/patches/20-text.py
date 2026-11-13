"""Insert the English: every src/text/script-en.json entry with text in one of `_layout.TEXT_FIELDS` (the first field
with text wins) goes to the expansion banks, reached by a DF jump written over the start of the Japanese
it replaces and ending with a DF back to the entry's `resume` (hand-found) or `end` (the end of
the Japanese run).

A draft (any field but `final`) for a label (a Japanese run of 12 characters or fewer that `is_label`) that is wider than the Japanese
(12 px a character) is gated: it starts with `DD fit <px> <fallback>` (17-natives.py), which at run time goes on to the
English only if it fits what is left of the window's line, and otherwise to a copy of the Japanese. A `final` is always inserted.
The detour needs the 4 bytes of a DF jump: a shorter run takes the fixed-length control codes after it into the span
(`extend_short`), copied after the English.
String-table entries (`table`) run as script too: every table's reader points the script reader at the string or
builds a `DE` call to it (88:93D8/9406/9420, 88:9530, 88:DC07, 88:D9C5), so they take the
same DF detour.
A Japanese run's leading D0-D2 codes (kept out of the drafts) are written back in front of the English.
A run followed by an `E1` wait first calls the native that clears its flag (17-natives.py).
A draft the font or the box can't take (no glyph, a word wider than a line) is left Japanese and listed.
A sentence (an entry with `members`) replaces its member runs and the name/number printing
codes between them: its English has a [name1]/[num2] marker for each code (`subst`), written back where it stands."""

import json
import re
from collections import Counter

import _layout
from en_text import TextError, condense, encode, layout, normalize, parse_addr, tokens, widths
from _layout import REPO, TextAllocator, put, snes_to_rom
import layout as text_layout
import script_vm

DF, WAIT_FOR_ANIMATION, NEWLINE, WAIT_FRAMES = 0xDF, 0xE1, 0xDB, 0xE0
ROW_TICK = 8  # the narration window's text delay: frames a 16 px character (the Japanese: 14 a row, 112 frames)
ROW_SLACK = 1  # frames a row of English takes besides its letters (one each) and blanks (the DB and the E0), measured
# Stat labels in the school / work panels (and the day's Gold / Earned / Spent): drawn in the condensed set, like the
# overview's labels, so the full words fit (C7 $11EC-$5FFF; the vacation box after it stays Japanese).
CONDENSED_LABELS = {'Vigor', 'Might', 'Intellect', 'Grace', 'Charm', 'Morality', 'Faith', 'Sin', 'Sensitivity', 'Stress',
                    'Etiquette', 'Cooking', 'Art', 'Cleaning', 'Speech', 'Temperance', 'Combat', 'Attack', 'Defense',
                    'Sorcery', 'Mana', 'Magic Def.', 'Gold', 'Earned', 'Spent'}


def condensed_label(key: str, entry: dict, text: str) -> bool:
    bank, off = parse_addr(key) >> 16, parse_addr(key) & 0xFFFF
    if text not in CONDENSED_LABELS:
        return False
    if (entry.get('table') or '').startswith('C7:0A8F['):  # the stat names the panels print (88:9530: DE <name> DB)
        return True
    return bank == 0xC7 and 0x11EC <= off < 0x6000 and not entry.get('table')


LABEL_CHARS, CHAR_PX = 12, 12  # a Japanese run this short is a label or menu item
MAX_LINE_PX = 16 * CHAR_PX  # the widest window seen: 16 characters a line
# String tables left Japanese: the item list draws garbled in its (staged-tile) list window; the others are data
# fragments the dump took for text
TABLES_OFF = {'C7:0796', 'C7:07B4', 'C7:0DEC', 'C7:1109', 'C7:1151'}
# Runs the dump took for text that are really a control code's arguments: never replaced. C7:6D8D / C7:6D8F are the
# vacation stat box's `DC 04 C7:6A5C` window setup (C7:6D8E); English there set window $DF and wiped $7F:0000-3FFF.
NOT_TEXT = {'C7:6D8D', 'C7:6D8F'}
MARKER = re.compile(r'\[(?:name|num)(\d+)\]')
PUNCT_ONLY = re.compile(r'[*\u2026\-,.!?\u00a1\u00bf\u3000 ]+')  # on the mask (export_script.py): the Japanese punctuation as placeholders
LEADING = re.compile(r'^(?:\{D([0-2])\})+')


def entries() -> dict[str, dict]:
    """The English script, src/text/script-en.json: per run its text fields (tried in _layout.TEXT_FIELDS order), its
    structure, `jp` (a layout mask of the Japanese: control codes and blanks kept, letters `x`) and `label`."""
    return json.loads((REPO / 'src' / 'text' / 'script-en.json').read_text())['entries']


def list_cells(entry: dict) -> int:
    """A shop list entry fills a 7-character row (18-windows.py widens those lists from 6)."""
    t = entry.get('table', '')
    return 7 if t.startswith('C7:041A[') and int(t[8:-1]) >= 54 else 0  # [54]+: the padded list copies (C7 $0694+)


def is_label(entry: dict) -> bool:
    """A menu item or a box label (kanji/katakana words, maybe a verb ending, or up to 5 characters), not a short sentence
    that may wrap onto a second line of a dialogue box: decided from the Japanese by tools/text/export_script.py."""
    return bool(entry.get('label'))


# Control codes a short run may be stretched over (code -> argument bytes): fixed length, absolute addresses only
# (not DD natives with inline arguments, not the F0-F9 jumps whose targets are bank-relative words)
SPAN_CODES = {0xD3: 7, 0xD4: 1, 0xD5: 4, 0xD6: 4, 0xD7: 2, 0xD8: 0, 0xD9: 0, 0xDA: 0, 0xDB: 0, 0xDC: 4, 0xDE: 3,
              0xDF: 3, 0xE0: 2, 0xE1: 0, 0xE2: 3, 0xE3: 2, 0xE4: 1, 0xE5: 5, 0xE6: 5, 0xEF: 0, 0xFC: 0}


def extend_short(rom: bytearray, end: int, start: int) -> tuple[bytes, int]:
    """A run under 4 bytes can't take a DF jump: take the control codes after it into the span (until it is 4 bytes)
    and run copies of them after the English. Returns (copied codes, new resume)."""
    tail, at = bytearray(), end
    while at - start < 4:
        op = rom[snes_to_rom(at)]
        if op not in SPAN_CODES or op == 0xE1:
            return b'', end
        n = 1 + SPAN_CODES[op]
        tail += rom[snes_to_rom(at):snes_to_rom(at) + n]
        at += n
        if op in (0xDF, 0xEF, 0xFC):  # EF: 0 bytes, ends a menu's items (vacation, C7:6CD0)
            break
    return bytes(tail), at


def leading_codes(jp: str, tight: bool = False) -> bytes:
    """`tight`: a narrow menu (the quest battle's, 4 characters) whose items don't fit after the 12 px blank (the pen
    rounds it to 16) and a space: 3 spaces (12 px) instead, still past the cursor's tile."""
    m = LEADING.match(jp or '')
    codes = bytes(0xD0 + int(d) for d in re.findall(r'\{D([0-2])\}', m.group(0))) if m else b''
    rest = (jp or '')[m.end():] if m else (jp or '')
    n = len(rest) - len(rest.lstrip('\u3000'))  # a menu item's cursor column: the 12 px blank(s), then a 4 px space so
    if tight and n:
        return codes + bytes([0x01, 0x20]) * 3
    return codes + bytes([FULL_SPACE]) * n + (bytes([0x01, 0x20]) if n else b'')  # the letters start past the cursor's tile


FULL_SPACE = 0x08  # the font's 12 px blank (the Japanese '\u3000')


def encode_rows(text: str, columns: int, tail: int = 0, center: bool = False, total_rows: int = 0) -> bytes:
    """A scrolling text (the opening narration, the credits) in a 16 px window, `columns` 8 px columns a row. The
    window's tilemap rows are reused as it scrolls, so every row is filled to the end as the Japanese does: the English
    (laid out here), VWF spaces to an even column, the game's 16 px blank (08) to the end, an E0 wait for the rest of
    the row's time (the Japanese: 8 frames a cell; the scroll keeps that pace on its own), then a new line (DB), which
    also keeps the VWF's word-wrap from reading the next row's first word as part of this row's last.
    ` / ` separates paragraphs (a blank row between; an empty paragraph is one more blank row), ` | ` breaks a line.
    `center` centres each row. `tail` blank cells follow; `total_rows` pads with blank rows to the Japanese row count."""
    w = widths()
    out = bytearray()
    rows = 0

    def row(line_text: str) -> None:
        nonlocal out, rows
        px = sum(w[c] for c in line_text)
        body = encode(line_text) if line_text else b''
        if center and line_text:
            n = (columns * 8 - px) // 2 // w[' ']
            body = bytes([0x01, 0x20]) * n + body
            px += n * w[' ']
        while -(-px // 8) % 2:
            body += bytes([0x01, 0x20])
            px += w[' ']
        blanks = (columns - -(-px // 8)) // 2
        wait = ROW_TICK * (columns // 2 - blanks) - len(body) // 2 - ROW_SLACK
        out += body + bytes([FULL_SPACE]) * blanks
        if wait > 0:
            out += bytes([WAIT_FRAMES]) + wait.to_bytes(2, 'little')
        out += bytes([NEWLINE])
        rows += 1

    for i, para in enumerate(text.split(' / ')):
        if i:
            row('')
        for piece in para.split(' | ') if para else []:
            if not piece.strip():
                row('')
                continue
            for line in layout(normalize(piece), w, columns * 8)[0]:
                row(''.join(str(t[1]) for t in line if t[0] == 'ch'))
    while rows < total_rows:
        row('')
    return bytes(out + bytes([FULL_SPACE]) * tail)


SOFT_SPACE = bytes([0x01, 0x00])  # 15-vwf.py vwf_soft
ZERO_ARG = {0xD0, 0xD1, 0xD2, 0xD8, 0xDA, 0xDB}  # codes with no arguments a merged short run may span


def blank_and_merge_short(rom: bytearray, merged: dict, in_sentence: set, targets: set) -> tuple[set, set]:
    """Runs under 4 bytes (no room for a DF jump). One marked `blank` is a particle the English around it already
    says (a name's particle wa, the honorific o split off a sentence by a jump target, a stutter after a wait): its bytes become D0, the
    code that only goes on reading. Otherwise, when only argument-less codes (DB, D8 DA, D0-D2) lie between it and the
    start of the next run with English, it joins that run: the next run's detour starts here instead, with this
    run's English and those codes in front (a menu's yes / no). Returns (blanked, merged into the next)."""
    blanked, into = set(), set()
    starts = {parse_addr(k): k for k in merged}
    for key, entry in merged.items():
        if (key in in_sentence or 'resume' in entry or entry.get('table') or key in NOT_TEXT
                or key in _layout.RESERVED_RUNS or key in _layout.TEXT_SKIP):
            continue
        start, end = parse_addr(key), parse_addr(entry['end'])
        if end - start >= 4 or end >> 16 != start >> 16:
            continue
        if not entry.get('blank') and extend_short(rom, end, start)[1] - start >= 4:
            continue  # the codes after it make room: the usual detour
        if entry.get('blank'):
            off = snes_to_rom(start)
            rom[off:off + end - start] = bytes([0xD0]) * (end - start)
            blanked.add(key)
            continue
        field = next((f for f in _layout.TEXT_FIELDS if entry.get(f)), '')
        if entry.get('nomerge'):  # maybe data, not text: left alone
            continue
        if field != 'final' and PUNCT_ONLY.fullmatch(re.sub(r'\{[^}]*\}', '', entry.get('jp', ''))):
            continue  # a middle dot between waits: its draft is invented

        at = end
        while rom[snes_to_rom(at)] in ZERO_ARG and at - end < 4:
            at += 1
        nxt = starts.get(at)
        if covers_target(start, targets):
            continue  # the next run's DF would start here and run over the jump into it
        if not field or not nxt or nxt in in_sentence or nxt == key or nxt in NOT_TEXT or nxt in _layout.RESERVED_RUNS:
            continue
        ne = merged[nxt]
        if 'resume' in ne or ne.get('table') or ne.get('subst') or '_start' in ne or ne.get('blank'):
            continue
        if not any(ne.get(f) for f in _layout.TEXT_FIELDS):
            continue
        try:
            text = entry[field].rstrip('. ') if len(entry['jp']) <= 3 else entry[field]
            words = encode(condense(normalize(text)) if condensed_label(key, entry, text) else normalize(text))
        except TextError:
            continue
        ne['_start'] = key
        ne['_prefix'] = leading_codes(entry.get('jp', '')) + words + bytes(rom[snes_to_rom(end):snes_to_rom(at)])
        into.add(key)
    return blanked, into


def waits_for_animation(rom: bytearray, addr: int) -> bool:
    """Whether the message goes on from `addr` to an E1 wait: through text (Japanese, or English reached by a DF
    detour), new lines, D0-D2, name calls (DE) and natives, following DF gotos, until a wait, page or other code."""
    for _ in range(600):
        off = snes_to_rom(addr)
        b = rom[off]
        if b == WAIT_FOR_ANIMATION:
            return True
        if b == DF:
            addr = int.from_bytes(rom[off + 1:off + 4], 'little')
            continue
        if b < 0x08:
            addr += 2  # a two-byte character, or an English letter (01 xx)
        elif b < 0xD0 or b in (0xD0, 0xD1, 0xD2, NEWLINE):
            addr += 1
        elif b == 0xDE:
            addr += 4
        elif b == 0xDD:
            target = int.from_bytes(rom[off + 1:off + 4], 'little')
            if target == _layout.NATIVE_FIT:
                n = 4  # <px> <24-bit fallback>
            elif target == _layout.NATIVE_CLEAR_WAIT:
                n = 0
            else:
                n, rewrites = script_vm.native_args(target)
                if rewrites:
                    return False
            addr += 4 + n
        else:
            return False
    return False


def encode_sentence(text: str, subst: list[str]) -> bytes:
    """English with [name1]/[num2] markers -> script bytes, each marker replaced by the game's printing code."""
    parts = MARKER.split(text.replace('\\[', '[').replace('\\]', ']'))  # models sometimes escape the brackets
    found = [int(n) for n in parts[1::2]]
    if sorted(found) != list(range(1, len(subst) + 1)):
        raise TextError(f'markers {found} != 1..{len(subst)}')
    out = bytearray()
    space = bytes([0x01, 0x20])  # encode() drops a space at either end of a piece: one next to a marker is kept
    for i, piece in enumerate(parts):
        if i % 2:
            out += bytes.fromhex(subst[int(piece) - 1])
            continue
        out += (space if i and piece[:1] == ' ' else b'') + encode(normalize(piece)) + (
            space if i < len(parts) - 1 and piece[-1:] == ' ' else b'')
    return bytes(out)


def english_sentence(entry: dict) -> bool:
    """An entry that inserts English prose (not a label, menu item, list entry or scrolling text)."""
    jp = entry.get('jp', '')
    return (any(entry.get(f) for f in _layout.TEXT_FIELDS) and not entry.get('table') and not entry.get('rows')
            and not entry.get('blank') and not (len(re.sub(r'\{[^}]*\}', '', jp)) <= LABEL_CHARS and is_label(entry)))


def joins_next(rom: bytearray, merged: dict, key: str, entry: dict, resume: int) -> bool:
    """Whether the Japanese line break (DB) at `resume` only separates this English sentence from the next one in the
    same box: the next run starts right after it and is English prose too."""
    if 'resume' in entry or rom[snes_to_rom(resume)] != NEWLINE or not english_sentence(entry):
        return False
    text = next((entry[f] for f in _layout.TEXT_FIELDS if entry.get(f)), '')
    if not re.search(r'[.!?…,]["\')]?\s*$', text):
        return False  # a heading ("Monthly Schedule (First Part)") keeps its own line
    nxt = merged.get(f'{resume + 1 >> 16:02X}:{resume + 1 & 0xFFFF:04X}')
    if nxt and (nxt.get('jp', '').startswith('\u3000') or str(nxt.get('final', '')).startswith('{01 20}')):
        return False  # a row of menu items (yes / no, C0:2EE2) keeps its own line
    return bool(nxt) and english_sentence(nxt) and not re.match(r'\{D[0-2]\}', nxt.get('jp', ''))


NOTES = REPO / 'src' / 'text' / 'LINE-NOTES.md'


def write_notes(notes: dict[str, list[str]]) -> None:
    """src/text/LINE-NOTES.md: the `final` lines the layout check says to rework, written by every build (only for
    lines whose window the build knows: tools/text/layout.py)."""
    out = ['# Line notes', '', 'Written by every build from the layout check: lines to rework. Only lines whose window '
           'the build knows are checked.', '']
    for title, rows in notes.items():
        out += [f'## {title} ({len(rows)})', ''] + [f'- {r}' for r in sorted(rows)] + ['']
    NOTES.write_text('\n'.join(out))


def covers_target(start: int, targets: set) -> bool:
    """A DF written at `start` takes 4 bytes: a jump into the 3 after it would land in the DF's address."""
    return any(divmod(t, 0x10000) in targets for t in range(start + 1, start + 4))


def reached_by_jumps_only(walked: dict, at: tuple) -> bool:
    """Nothing reads on into `at` from the token before it (it follows a jump, a return or a table) and it isn't a
    message start the game code points at: every way in is a DE/DF/F6-F9 argument or a table entry, so it can move."""
    if at in script_vm.entry_points() or at in script_vm.message_starts():
        return False
    return not any(b == at[0] and n == at[1] and c not in script_vm.ENDS for (b, _o), (c, _a, n) in walked.items())


def repoint(rom: bytearray, walked: dict, old: tuple, new: int) -> None:
    """Every walked jump, call, branch and table entry that goes to `old` goes to `new` instead (same bank)."""
    lo = (new & 0xFFFF).to_bytes(2, 'little')
    for (bank, off), (code, args, _n) in walked.items():
        pos = snes_to_rom((bank << 16) | off) + 1
        slots = {0xDE: [(0, 2)], 0xDF: [(0, 2)], 0xF6: [(0, None), (2, None)], 0xF7: [(0, 2), (3, 5)],
                 0xF8: [(3, None), (5, None)], 0xF9: [(3, 5), (6, 8)]}.get(code, [])
        for w, b in slots:
            if len(args) > w + 1 and (args[b] if b is not None else bank, args[w] | args[w + 1] << 8) == old:
                rom[pos + w:pos + w + 2] = lo
    for bank, p, _width in script_vm.TABLE_REFS.get(old, ()):
        rom[snes_to_rom((bank << 16) | p):snes_to_rom((bank << 16) | p) + 2] = lo


def apply(rom: bytearray) -> None:
    alloc = TextAllocator()
    orig = bytes(rom)  # the script as the game shipped it: runs earlier in the loop rewrite bytes later ones look at
    done, waits, gated, skipped, failed = 0, 0, 0, Counter(), []
    merged = entries()
    for key, entry in list(merged.items()):  # a sentence whose English can't be built doesn't replace its runs
        if entry.get('subst'):
            field = next((f for f in _layout.TEXT_FIELDS if entry.get(f)), '')
            try:
                if field:
                    encode_sentence(entry[field], entry['subst'])
            except TextError as e:
                failed.append(f'{key}: {e}')
                merged[key] = {k: v for k, v in entry.items() if k not in _layout.TEXT_FIELDS}
    in_sentence = {m for k, e in merged.items() if e.get('subst') and any(e.get(f) for f in _layout.TEXT_FIELDS)
                   for m in e['members'] if m != k}
    walked = script_vm.walk_entry_points()[1]
    targets = script_vm.jump_targets(walked)
    blanked, merged_into = blank_and_merge_short(rom, merged, in_sentence, targets)
    dead: list[list[int]] = []  # [next free, end) bytes of a run behind its own DF: no jump lands there any more
    relocate: list[tuple[str, int, bytes]] = []  # (key, start, body): a head too short for its DF, placed in `dead`
    window_of = text_layout.window_map(walked, rom, snes_to_rom)
    indented = 0
    joined = 0
    fit = Counter()
    fit_report: list[str] = []
    notes: dict[str, list[str]] = {'Too long for its box: must be shorter (the box scrolls and the top line is lost)': [],
                                   'A lone word on the last line (reword so the line ends fuller, or shorter)': []}
    for key, entry in merged.items():
        if key in blanked:
            skipped['blanked (a particle the English around it carries)'] += 1
            continue
        if key in merged_into:
            skipped['short run merged into the next'] += 1
            continue
        field = next((f for f in _layout.TEXT_FIELDS if entry.get(f)), '')
        text = entry.get(field, '')
        if key in in_sentence:
            skipped['part of a translated sentence'] += 1
            continue
        if not text:
            skipped['no text'] += 1
            continue
        if field != 'final' and PUNCT_ONLY.fullmatch(re.sub(r'\{[^}]*\}', '', entry.get('jp', ''))):
            skipped['punctuation only (a drafted "Brace yourself!" for a middle dot between waits)'] += 1
            continue
        if entry.get('table', '').split('[')[0] in TABLES_OFF:
            skipped['string table left Japanese'] += 1
            continue
        if key in NOT_TEXT:
            skipped['not text (control code arguments)'] += 1
            continue
        if key in _layout.RESERVED_RUNS:
            skipped['patched by another module'] += 1
            continue
        if key in _layout.TEXT_SKIP:
            skipped['skipped (--skip)'] += 1
            continue
        start = parse_addr(entry.get('_start', key))
        if divmod(start, 0x10000) not in walked and not entry.get('table') and 'resume' not in entry:
            skipped['start is not a script token (inside a code\'s arguments)'] += 1  # a DF there corrupts the code
            continue
        resume = parse_addr(entry.get('resume') or entry['end'])
        if entry.get('table') and 'resume' not in entry and rom[snes_to_rom(resume) - 1] == 0xFC:
            resume -= 1  # a table string's `end` is past its FC terminator: resume on the FC, not the next string
        tail = b''
        if resume - start < 4 and 'resume' not in entry and resume >> 16 == start >> 16:
            tail, resume = extend_short(rom, resume, start)
        short_head = resume - start < 4 and 'resume' not in entry and divmod(resume, 0x10000) in targets
        if short_head and not reached_by_jumps_only(walked, divmod(start, 0x10000)):
            skipped['Japanese run under 4 bytes, before a jump target (fallen into, so it cannot move)'] += 1
            continue
        if not short_head and (resume >> 16 != start >> 16 and 'resume' not in entry or resume - start < 4 and 'resume' not in entry):
            skipped['Japanese run under 4 bytes'] += 1
            continue
        if not short_head and covers_target(start, targets):
            skipped['a jump lands inside the 4 bytes a DF would take'] += 1
            continue
        table = bool(entry.get('table'))
        list_word = orig[snes_to_rom(start) - 4] == 0xDF or orig[snes_to_rom(resume)] == 0xDF and not table
        gate = None
        jp_chars = len(re.sub(r'\{[^}]*\}', '', entry.get('jp', '')))
        table = bool(entry.get('table'))  # a table string can be drawn in any window (status, overview): always gated
        if table or field != 'final' and not entry.get('subst') and not list_word and 0 < jp_chars <= LABEL_CHARS and is_label(entry):  # a reviewed `final` is trusted
            px = sum(widths().get(v, 0) for k, v in tokens(normalize(text)) if k == 'ch')
            if table or px > jp_chars * CHAR_PX:
                if px > min(MAX_LINE_PX, 255) or resume >> 16 != start >> 16:
                    skipped['draft wider than any box'] += 1
                    continue
                gate = (px, bytes(rom[snes_to_rom(start):snes_to_rom(resume)]))
        if 0 < jp_chars <= LABEL_CHARS and field not in ('final', 'labels') and not entry.get('subst') and is_label(entry) and not re.search(r'[.!?]', entry.get('jp', '')) and not condensed_label(key, entry, text):
            text = text.rstrip('. ')  # a label or menu item has no full stop (a stat label keeps its abbreviation's)
        if list_word and field != 'final' and not re.search(r'[.!?]', entry.get('jp', '')) and not condensed_label(key, entry, text):
            text = text.rstrip('. ')  # a word from a list that jumps on into a sentence (the dish parts): no full stop
        try:
            if entry.get('rows'):
                words = encode_rows(text, entry['rows'], entry.get('tail', 0), entry.get('center', False),
                                    entry.get('total_rows', 0))
            else:
                words = encode_sentence(text, entry['subst']) if entry.get('subst') else encode(condense(normalize(text)) if condensed_label(key, entry, text) else normalize(text))
            jp_raw = entry.get('jp', '')
            list_pad = b''
            if entry.get('table') and (jp_raw.endswith('\u3000') or list_cells(entry)):  # a list entry padded to fill its row: the game
                cells = len(re.sub(r'\{[^}]*\}', '', jp_raw))  # wraps once the column reaches the line; pad the
                px = sum(widths().get(v, 0) for k, v in tokens(normalize(text)) if k == 'ch')  # English to the same
                # to exactly one pixel past the cells (the VWF and `fit` start a new line there); a space's 4 px would
                # overshoot by up to 4, and the overshoot shifts the next row right
                list_pad = text_layout.blank(max(cells, list_cells(entry)) * CHAR_PX + 1 - px)
                words += list_pad
            lead = entry.get('_prefix', b'') + leading_codes(entry.get('jp', ''), entry.get('tight', False))
            menu_at = None
            if not table and not entry.get('subst') and 0 < jp_chars <= LABEL_CHARS and is_label(entry):
                menu_at = text_layout.menu_code(walked, divmod(start, 0x10000))
                where = window_of(divmod(start, 0x10000)) if menu_at else None
                if where:  # a menu item: indent past the cursor exactly, instead of the Japanese blank and pad spaces
                    o = snes_to_rom(menu_at)
                    pad = text_layout.blank(entry['indent'] if 'indent' in entry  # `indent`: px, for a menu whose
                                            else text_layout.indent_px(rom[o + 2], where[0].x))  # cursor sits outside the box (town)
                    codes = re.match(r'^(?:\{D[0-2]\})*', entry.get('jp', '')).group(0)
                    lead = entry.get('_prefix', b'') + bytes(0xD0 + int(d) for d in re.findall(r'D([0-2])', codes)) + pad
                    words = words.replace(bytes([NEWLINE]), bytes([NEWLINE]) + pad)
                    indented += 1
                else:
                    menu_at = None
            body = (lead.rstrip(bytes([FULL_SPACE])) if table else lead) + words  # a list draws its own cursor column
            if (not menu_at and not entry.get('rows') and not list_cells(entry) and not (table and jp_raw.endswith('\u3000'))
                    and not (not table and 0 < jp_chars <= LABEL_CHARS and is_label(entry) and not list_word)
                    and re.match(r'[A-Za-z0-9"(\[]', normalize(text))):
                body = body[:len(body) - len(words)] + SOFT_SPACE + words  # a space only where this run goes on a line after other English (15-vwf.py)
            if (not table and not entry.get('subst') and (0 < jp_chars <= LABEL_CHARS and is_label(entry) or field == 'labels')
                    and rom[snes_to_rom(parse_addr(entry['end']))] in (0xDB, 0xEF) and not lead.endswith(bytes([FULL_SPACE]))
                    and not lead.endswith(bytes([0x01, 0x20])) and words[:2] != bytes([0x01, 0x20]) and not entry.get('nopad')
                    and not menu_at):
                body = lead + bytes([0x01, 0x20]) + words  # a menu item (label before a new line or the menu's end): 4 px after the cursor
            where = window_of(divmod(start, 0x10000))
            if not where or not where[1]:
                fit['no window known (set by game code) or not at a line start'] += 1
            else:
                win = where[0]
                res = text_layout.simulate(body[:len(body) - len(list_pad)], win)  # the row's pad is meant to cross the edge
                menu = 0 < jp_chars <= LABEL_CHARS and is_label(entry) and not table
                if res.broken_words:
                    why = 'a word cut in the middle'
                elif menu and res.wraps:
                    why = 'a label or menu item wraps'
                elif res.max_lines > win.lines:  # the box scrolls up with no wait (87:88C6): the top line is lost
                    why = f'{res.max_lines} lines in a {win.lines}-line box'
                else:
                    why = ''
                if not why and res.widows and field == 'final':
                    notes['A lone word on the last line (reword so the line ends fuller, or shorter)'].append(
                        f'`{key}` ends on **{res.widows[0]}**: {text}')
                if why and field == 'final' and res.max_lines > win.lines and not res.broken_words and not (menu and res.wraps):
                    fit['final over the box (listed: rewrite it shorter)'] += 1
                    fit_report.insert(0, f'{key} [final] {why}: {text[:60]!r}  <- REWRITE')
                    notes['Too long for its box: must be shorter (the box scrolls and the top line is lost)'].append(
                        f'`{key}` {why}: {text}')
                    why = ''
                fit[why or 'checked'] += 1
                if why and field == 'final':
                    raise SystemExit(f'{key}: the final does not fit its window ({win.chars} characters): {why}: {text!r}')
                if why:
                    short = sum(widths().get(v, 0) for k, v in tokens(normalize(text)) if k == 'ch')
                    fit_report.insert(0, f'{key} [{field}] left Japanese, {why}: {text[:50]!r} in a {win.chars}-character window '
                                         f'({win.limit_px} px; the English alone is {short} px)')
                    skipped[f'draft does not fit its window ({why})'] += 1
                    continue
            if waits_for_animation(rom, resume):
                body = bytes([0xDD]) + _layout.NATIVE_CLEAR_WAIT.to_bytes(3, 'little') + body
                waits += 1
        except TextError as e:
            failed.append(f'{key}: {e}')
            continue
        if not tail and joins_next(rom, merged, key, entry, resume):
            body += bytes([0x01, 0x20])  # the Japanese line break before the next English sentence: a space, so
            resume += 1                  # the VWF wraps the two as one paragraph (no lone word at a line's end)
            joined += 1
        body += tail + bytes([DF]) + resume.to_bytes(3, 'little')
        if gate:
            setup = len(gate[1]) - len(gate[1].lstrip(bytes([0xD0, 0xD1, 0xD2])))
            setup = setup if body.startswith(gate[1][:setup]) else 0  # the window codes in front run before the gate,
            fallback = gate[1][setup:] + bytes([DF]) + resume.to_bytes(3, 'little')  # which measures the window they set
            fb_at = alloc.alloc(len(fallback))
            put(rom, fb_at, fallback)
            body = (body[:setup] + bytes([0xDD]) + _layout.NATIVE_FIT.to_bytes(3, 'little') + bytes([gate[0]])
                    + fb_at.to_bytes(3, 'little') + body[setup:])
            gated += 1
        if short_head:
            relocate.append((key, start, body))
            continue
        at = alloc.alloc(len(body))
        put(rom, at, body)
        off = snes_to_rom(start)
        rom[off:off + 4] = bytes([DF]) + at.to_bytes(3, 'little')
        done += 1
        if not entry.get('table') and 'resume' not in entry and not entry.get('subst') and not gate:
            end_ = min(resume, parse_addr(entry['end']))
            if not any(divmod(t, 0x10000) in targets for t in range(start + 4, end_)):
                dead.append([start + 4, end_])
    for key, start, body in relocate:  # a short head reached only by jumps: its DF goes in a dead stretch of its bank
        spot = next((d for d in dead if d[0] >> 16 == start >> 16 and d[1] - d[0] >= 4), None)
        if not spot:
            skipped['Japanese run under 4 bytes, before a jump target (no room in its bank)'] += 1
            continue
        at = alloc.alloc(len(body))
        put(rom, at, body)
        new = spot[0]
        spot[0] += 4
        rom[snes_to_rom(new):snes_to_rom(new) + 4] = bytes([DF]) + at.to_bytes(3, 'little')
        repoint(rom, walked, divmod(start, 0x10000), new)
        done += 1
        skipped['(moved: a short head before a jump target, its DF in a dead stretch)'] += 0
        print(f'  {key}: under 4 bytes before a jump target: DF moved to ${new >> 16:02X}:{new & 0xFFFF:04X}, jumps to it repointed')
    print(f'  text: {done} inserted, {sum(skipped.values())} left Japanese ({dict(skipped)}), '
          f'{waits} before an E1 wait, {gated} labels gated on the box width, {len(failed)} drafts the font or box rejected; used to ${alloc.bank:02X}:{alloc.off:04X}')
    write_notes(notes)
    print(f'  {joined} Japanese line breaks between two English sentences made a space')
    print(f'  layout: {dict(fit)}; {indented} menu items indented past their cursor')
    for line in [l for l in fit_report if "REWRITE" in l] + [l for l in fit_report if "REWRITE" not in l][:12]:
        print('    ' + line)
    for why, n in Counter(f.split(': ', 1)[1] for f in failed).most_common(8):
        print(f'    {n:4d} x {why}')
