#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


class StartupPatchError(RuntimeError):
    pass


PATCHES = (
    (0x0069B8C6, bytes.fromhex("74 24"), bytes.fromhex("74 22")),
    (0x0069B8E6, bytes.fromhex("32 C0"), bytes.fromhex("B0 01")),
    (
        0x00685F9C,
        bytes.fromhex("0F 84 DF 00 00 00"),
        bytes.fromhex("E9 E0 00 00 00 90"),
    ),
    (
        0x006CF957,
        bytes.fromhex("8D 45 E0 0F 57 C0 50 66 0F"),
        bytes.fromhex("C6 47 4C 00 E9 43 01 00 00"),
    ),
    (
        0x0092B82A,
        bytes.fromhex("0F 84 8D 01 00 00"),
        bytes.fromhex("E9 8E 01 00 00 90"),
    ),
    (
        0x006A1CE1,
        bytes.fromhex("0F 85 FE 00 00 00"),
        bytes.fromhex("E9 FF 00 00 00 90"),
    ),
    (
        0x006A1E03,
        bytes.fromhex("0F 85 D8 00 00 00"),
        bytes.fromhex("E9 D9 00 00 00 90"),
    ),
    (
        0x008BCFF0,
        bytes.fromhex("55 8B EC 83 7D 0C 00 8B 45 08 75"),
        bytes.fromhex("8B 44 24 04 C7 00 00 00 00 00 C3"),
    ),
    (
        0x008D3A02,
        bytes.fromhex(
            "C7 47 48 01 00 00 00 "
            "8B 0D D0 A1 93 01 "
            "E8 1C 5F AB FF "
            "8B F0 8D 45 EC"
        ),
        bytes.fromhex(
            "C7 47 48 01 00 00 00 "
            "6A 00 6A 00 8B CF "
            "E8 4C 7F 00 00 "
            "E9 6A 00 00 00"
        ),
    ),
)

GUARDS = (
    (0x00BACDD0, bytes.fromhex("31 C0 C3 90 90 90 90")),
    (0x009168B0, bytes.fromhex("31 C0 C2 18 00")),
)


def _slice(data: bytes, offset: int, size: int) -> bytes:
    end = offset + size
    if end > len(data):
        raise StartupPatchError(
            f"AMS image is too small for startup site 0x{offset:08X}"
        )
    return data[offset:end]


def patch_bytes(data: bytes) -> bytes:
    for offset, expected in GUARDS:
        actual = _slice(data, offset, len(expected))
        if actual != expected:
            raise StartupPatchError(
                f"startup guard mismatch at 0x{offset:08X}: "
                f"{actual.hex(' ')} != {expected.hex(' ')}"
            )

    output = bytearray(data)

    for offset, before, after in PATCHES:
        actual = _slice(data, offset, len(before))
        if actual != before:
            raise StartupPatchError(
                f"startup site mismatch at 0x{offset:08X}: "
                f"{actual.hex(' ')} != {before.hex(' ')}"
            )
        output[offset : offset + len(after)] = after

    return bytes(output)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    args.output.write_bytes(patch_bytes(args.input.read_bytes()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
