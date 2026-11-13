"""Grow the ROM to 4 MiB (banks $E0-$FF are new, zero-filled) for the English script, and say so in the header.

Nothing in the base game reads $E0-$FF, so the mirror of $C0-$DF is not needed."""

from _layout import ROM_SIZE

HEADER = 0xFFC0
ROM_SIZE_BYTE = HEADER + 0x17  # log2(KiB): $0B = 2 MiB, $0C = 4 MiB


def apply(rom: bytearray) -> None:
    rom.extend(bytes(ROM_SIZE - len(rom)))
    rom[ROM_SIZE_BYTE] = 0x0C
