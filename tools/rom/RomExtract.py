"""Shared ROM access: the base ROM, HiROM address mapping, checksum guard."""

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROM_PATH = REPO / 'roms' / 'base.sfc'
ROM_MD5 = '135ad0c718e88aaa9de9ce848b47753a'  # Princess Maker - Legend of Another World (Japan), 2 MiB, no copier header
ROM_SIZE = 0x200000

_cache: bytes | None = None


def rom() -> bytes:
    """The unmodified base ROM, verified against ROM_MD5."""
    global _cache
    if _cache is None:
        data = ROM_PATH.read_bytes()
        got = hashlib.md5(data).hexdigest()
        if got != ROM_MD5:
            raise SystemExit(f'{ROM_PATH} md5 {got} != expected {ROM_MD5} (wrong or modified base ROM)')
        _cache = data
    return _cache


def snes_to_rom(addr: int) -> int:
    """HiROM mapping: banks C0-FF are the ROM linearly; banks 00-3F / 80-BF map $8000-$FFFF to the same 64K block.

    The ROM is 2 MiB, so banks $E0-$FF (and $40-$5F's upper half) mirror $C0-$DF.
    """
    bank = (addr >> 16) & 0xFF
    off = addr & 0xFFFF
    if bank >= 0xC0 or 0x40 <= bank <= 0x7D:
        return ((bank & 0x3F) * 0x10000 + off) % ROM_SIZE
    if off < 0x8000:
        raise ValueError(f'${addr:06X} is not ROM (system area)')
    return ((bank & 0x3F) * 0x10000 + off) % ROM_SIZE


def rom_to_snes(offset: int) -> int:
    """File offset -> the $C0-$DF bank address."""
    return 0xC00000 + offset


def read_bytes(addr: int, length: int, data: bytes | None = None) -> bytes:
    at = snes_to_rom(addr)
    return (data or rom())[at : at + length]
