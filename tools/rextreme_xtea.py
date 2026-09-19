#!/usr/bin/env python3
"""Asphalt ReXtreme XTEA asset utility for Windows build 1.7.3.8 x86.

Verified container format:
  uint16 LE type
  XTEA-encrypted payload, 8-byte blocks
Decrypted payload:
  uint32 LE body_length
  uint32 LE CRC32(body)
  body bytes
  zero padding (always 1..8 bytes)
"""
from __future__ import annotations

import argparse
import struct
import zlib
import zipfile
from pathlib import Path

KEY_SOURCE = b"Unhandled field type (%d) in standard profile (%s)"
DELTA = 0x9E3779B9
MASK = 0xFFFFFFFF


def derive_key(source: bytes = KEY_SOURCE) -> bytes:
    key = bytearray(16)
    for i, value in enumerate(source):
        key[i & 15] ^= value
    return bytes(key)


KEY_BYTES = derive_key()
KEY = struct.unpack("<4I", KEY_BYTES)


def decrypt_block(block: bytes) -> bytes:
    if len(block) != 8:
        raise ValueError("XTEA blocks must be exactly 8 bytes")
    v0, v1 = struct.unpack("<2I", block)
    total = (DELTA * 32) & MASK
    for _ in range(32):
        v1 = (
            v1
            - (((((v0 << 4) & MASK) ^ (v0 >> 5)) + v0)
               ^ (total + KEY[(total >> 11) & 3]))
        ) & MASK
        total = (total - DELTA) & MASK
        v0 = (
            v0
            - (((((v1 << 4) & MASK) ^ (v1 >> 5)) + v1)
               ^ (total + KEY[total & 3]))
        ) & MASK
    return struct.pack("<2I", v0, v1)


def encrypt_block(block: bytes) -> bytes:
    if len(block) != 8:
        raise ValueError("XTEA blocks must be exactly 8 bytes")
    v0, v1 = struct.unpack("<2I", block)
    total = 0
    for _ in range(32):
        v0 = (
            v0
            + (((((v1 << 4) & MASK) ^ (v1 >> 5)) + v1)
               ^ (total + KEY[total & 3]))
        ) & MASK
        total = (total + DELTA) & MASK
        v1 = (
            v1
            + (((((v0 << 4) & MASK) ^ (v0 >> 5)) + v0)
               ^ (total + KEY[(total >> 11) & 3]))
        ) & MASK
    return struct.pack("<2I", v0, v1)


def decode_xtea(data: bytes, verify_crc: bool = True) -> tuple[int, bytes]:
    if len(data) < 10:
        raise ValueError("XTEA file is too short")

    file_type = struct.unpack_from("<H", data, 0)[0]
    encrypted = data[2:]
    if len(encrypted) % 8:
        raise ValueError("Encrypted payload is not 8-byte aligned")

    plain = b"".join(
        decrypt_block(encrypted[i:i + 8])
        for i in range(0, len(encrypted), 8)
    )

    body_length, stored_crc = struct.unpack_from("<II", plain, 0)
    if body_length > len(plain) - 8:
        raise ValueError(f"Invalid body length: {body_length}")

    body = plain[8:8 + body_length]
    padding = plain[8 + body_length:]
    if any(padding):
        raise ValueError("Non-zero padding found")

    actual_crc = zlib.crc32(body) & MASK
    if verify_crc and actual_crc != stored_crc:
        raise ValueError(
            f"CRC mismatch: stored={stored_crc:08x}, actual={actual_crc:08x}"
        )
    return file_type, body


def encode_xtea(body: bytes, file_type: int = 1) -> bytes:
    crc = zlib.crc32(body) & MASK
    payload = struct.pack("<II", len(body), crc) + body

    # The original writer always emits padding, including a full 8-byte block
    # when the header+body is already aligned.
    padding_length = 8 - (len(payload) % 8)
    payload += b"\x00" * padding_length

    encrypted = b"".join(
        encrypt_block(payload[i:i + 8])
        for i in range(0, len(payload), 8)
    )
    return struct.pack("<H", file_type) + encrypted


def detect_plain_suffix(body: bytes) -> str:
    stripped = body.lstrip()
    if stripped.startswith(b"<?xml") or stripped.startswith(b"<"):
        return ".xml"
    if stripped.startswith(b"{") or stripped.startswith(b"["):
        return ".json"
    return ".bin"


def decrypt_file(source: Path, destination: Path) -> None:
    file_type, body = decode_xtea(source.read_bytes())
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(body)
    print(
        f"decrypted type={file_type}, bytes={len(body)}: "
        f"{source} -> {destination}"
    )


def encrypt_file(source: Path, destination: Path, file_type: int) -> None:
    body = source.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(encode_xtea(body, file_type))
    print(
        f"encrypted type={file_type}, bytes={len(body)}: "
        f"{source} -> {destination}"
    )


def verify_file(source: Path) -> None:
    original = source.read_bytes()
    file_type, body = decode_xtea(original)
    rebuilt = encode_xtea(body, file_type)
    if rebuilt != original:
        raise SystemExit(f"round-trip mismatch: {source}")
    print(
        f"OK type={file_type} body={len(body)} "
        f"CRC={zlib.crc32(body) & MASK:08x} {source}"
    )


def extract_xmlbin(source: Path, output: Path) -> None:
    encrypted_root = output / "encrypted"
    decrypted_root = output / "decrypted"
    encrypted_root.mkdir(parents=True, exist_ok=True)
    decrypted_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(source, "r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue

            data = archive.read(info)
            encrypted_path = encrypted_root / Path(info.filename)
            encrypted_path.parent.mkdir(parents=True, exist_ok=True)
            encrypted_path.write_bytes(data)

            if info.filename.lower().endswith(".xtea"):
                file_type, body = decode_xtea(data)
                relative = Path(info.filename).with_suffix(
                    detect_plain_suffix(body)
                )
                decoded_path = decrypted_root / relative
                decoded_path.parent.mkdir(parents=True, exist_ok=True)
                decoded_path.write_bytes(body)
                print(
                    f"{info.filename}: type={file_type}, "
                    f"{len(body)} decoded bytes -> {relative}"
                )


def repack_xmlbin(
    original: Path,
    edited_root: Path,
    output: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    replaced = 0

    with zipfile.ZipFile(original, "r") as source_archive:
        with zipfile.ZipFile(output, "w") as output_archive:
            for info in source_archive.infolist():
                data = source_archive.read(info)

                if (
                    not info.is_dir()
                    and info.filename.lower().endswith(".xtea")
                ):
                    file_type, body = decode_xtea(data)
                    relative = Path(info.filename).with_suffix(
                        detect_plain_suffix(body)
                    )
                    edited = edited_root / relative
                    if edited.is_file():
                        data = encode_xtea(edited.read_bytes(), file_type)
                        replaced += 1
                        print(f"repacked {info.filename} from {edited}")

                # Passing the original ZipInfo keeps timestamps, attributes and
                # compression method used by the source xml.bin.
                output_archive.writestr(info, data)

    print(f"Wrote {output}; replaced {replaced} entries")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Asphalt ReXtreme XTEA utility for build 1.7.3.8 x86"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    cmd = sub.add_parser("decrypt")
    cmd.add_argument("source", type=Path)
    cmd.add_argument("destination", type=Path)

    cmd = sub.add_parser("encrypt")
    cmd.add_argument("source", type=Path)
    cmd.add_argument("destination", type=Path)
    cmd.add_argument("--type", type=int, default=1)

    cmd = sub.add_parser("verify")
    cmd.add_argument("source", type=Path)

    cmd = sub.add_parser("extract-xmlbin")
    cmd.add_argument("source", type=Path)
    cmd.add_argument("output", type=Path)

    cmd = sub.add_parser("repack-xmlbin")
    cmd.add_argument("original", type=Path)
    cmd.add_argument("edited_root", type=Path)
    cmd.add_argument("output", type=Path)

    args = parser.parse_args()

    if args.command == "decrypt":
        decrypt_file(args.source, args.destination)
    elif args.command == "encrypt":
        encrypt_file(args.source, args.destination, args.type)
    elif args.command == "verify":
        verify_file(args.source)
    elif args.command == "extract-xmlbin":
        extract_xmlbin(args.source, args.output)
    elif args.command == "repack-xmlbin":
        repack_xmlbin(args.original, args.edited_root, args.output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
