#!/usr/bin/env python3
"""Create a lab-only copy of AMS.exe with IMAGE_DLLCHARACTERISTICS_APPCONTAINER cleared.

The source is never modified. By default the exact known Campaign-patched
1.7.3.10 AMS.exe hash is required.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

EXPECTED_SHA256 = "56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3"
IMAGE_DLLCHARACTERISTICS_APPCONTAINER = 0x1000


class PEError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pe_offsets(data: bytes) -> tuple[int, int]:
    if len(data) < 0x100 or data[:2] != b"MZ":
        raise PEError("Not a PE/MZ executable.")
    peoff = struct.unpack_from("<I", data, 0x3C)[0]
    if peoff + 0x78 > len(data) or data[peoff:peoff + 4] != b"PE\0\0":
        raise PEError("Invalid PE header.")
    coff = peoff + 4
    optional = coff + 20
    magic = struct.unpack_from("<H", data, optional)[0]
    if magic != 0x10B:
        raise PEError(f"Expected PE32/x86 optional header, got {magic:#x}.")
    return optional + 64, optional + 70


def make_no_appcontainer(data: bytes) -> tuple[bytes, dict]:
    checksum_off, dll_off = pe_offsets(data)
    work = bytearray(data)

    old_checksum = struct.unpack_from("<I", work, checksum_off)[0]
    old_flags = struct.unpack_from("<H", work, dll_off)[0]
    if not (old_flags & IMAGE_DLLCHARACTERISTICS_APPCONTAINER):
        raise PEError("Source PE does not have APPCONTAINER set.")

    new_flags = old_flags & ~IMAGE_DLLCHARACTERISTICS_APPCONTAINER
    struct.pack_into("<H", work, dll_off, new_flags)
    struct.pack_into("<I", work, checksum_off, 0)

    return bytes(work), {
        "checksum_offset": checksum_off,
        "dll_characteristics_offset": dll_off,
        "old_checksum": old_checksum,
        "old_dll_characteristics": old_flags,
        "new_dll_characteristics": new_flags,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--allow-unknown-hash", action="store_true")
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    data = source.read_bytes()
    source_hash = sha256(data)

    if not args.allow_unknown_hash and source_hash != EXPECTED_SHA256:
        raise SystemExit(
            "Refusing unknown AMS.exe hash.\n"
            f"Expected: {EXPECTED_SHA256}\n"
            f"Actual:   {source_hash}"
        )

    patched, meta = make_no_appcontainer(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patched)

    print(f"source_sha256={source_hash}")
    print(f"output_sha256={sha256(patched)}")
    print(
        f"dll_characteristics={meta['old_dll_characteristics']:#06x}"
        f"->{meta['new_dll_characteristics']:#06x}"
    )
    print(f"output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
