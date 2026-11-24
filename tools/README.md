# tools/

Scripts run by hand with `python3 -I` (stdlib only, plus Pillow for graphics). They read the base ROM from
`roms/base.sfc` (not included). Each file's first comment says what it does and how to run it.

## rom/: reading and building the ROM

- `build.py`: base ROM + `src/patches/*.py` in name order (and `src/gamefix/` for the variants) -> `build/*.sfc` + `build/*.ips`.
- `release.py`: builds all three variants and publishes their IPS patches as a GitHub release (`gh`).
- `RomExtract.py`: the base ROM (md5-checked) and HiROM address mapping.
- `ips.py`: make and apply IPS patches.
- `asm65816.py`: a small two-pass 65816 assembler used by the patch modules.
- `disasm.py`: 65816 disassembly from the ROM (`disasm.py C08000 40 [--m8] [--x8]`).
- `search_text.py`: find text by Shift-JIS, half-width kana, or relative search.
- `free_space.py`: runs of `00`/`FF` in the base ROM, longest first.

## text/: the script

- `dump_script.py`: dump every script run and string table as font codes (`--charmap` to decode them).
- `script_vm.py`: the script language and a walker over it from the game's entry points.
- `en_text.py`: English encoding and pixel-width word wrap for the variable-width font.
- `layout.py`: window sizes and line checks for the insertion; `window_runs.json` maps runs to their windows.
- `jp_font.py`: the ROM's 16x16 font as labelled contact sheets.

## gfx/: graphics

- `lz.py`: the game's LZ compression formats (decode and encode).
- `find_asset.py`: locate a compressed asset by its contents.
- `render_bg.py`: render a BG layer from a VRAM/CGRAM dump.
- `make_banner.py`: draws the harvest festival banner (`src/font/festival-banner.png`).
