#!/usr/bin/env python3
"""Hash-guarded binary patcher for Asphalt ReXtreme.

Only applies explicit byte patches to explicitly supported hashes.
Writes atomically, validates every original byte sequence, and can verify a
known final hash from the manifest. Re-running against an already-patched file
is safe when patched_sha256 is present.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


class PatchError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_hex(value: str) -> bytes:
    compact = "".join(value.split())
    if len(compact) % 2:
        raise PatchError(f"Invalid hex string length: {value!r}")
    try:
        return bytes.fromhex(compact)
    except ValueError as exc:
        raise PatchError(f"Invalid hex string: {value!r}") from exc


@dataclass(frozen=True)
class BytePatch:
    name: str
    offset: int
    before: bytes
    after: bytes


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("files"), list):
        raise PatchError("Manifest must contain a files array.")
    return data


def validate_patch(raw: dict) -> BytePatch:
    name = str(raw.get("name", "unnamed patch"))
    offset = int(raw["offset"])
    before = parse_hex(raw["before"])
    after = parse_hex(raw["after"])
    if offset < 0:
        raise PatchError(f"{name}: negative offset")
    if len(before) != len(after):
        raise PatchError(f"{name}: before/after sizes differ")
    if not before:
        raise PatchError(f"{name}: empty byte patch")
    return BytePatch(name=name, offset=offset, before=before, after=after)


def apply_to_bytes(data: bytes, patches: list[BytePatch]) -> bytes:
    work = bytearray(data)
    occupied: list[tuple[int, int, str]] = []

    for patch in patches:
        end = patch.offset + len(patch.before)
        if end > len(work):
            raise PatchError(f"{patch.name}: offset outside file")

        for old_start, old_end, old_name in occupied:
            if patch.offset < old_end and end > old_start:
                raise PatchError(
                    f"{patch.name}: overlaps patch {old_name} "
                    f"(0x{patch.offset:X}-0x{end:X})"
                )

        found = bytes(work[patch.offset:end])
        if found != patch.before:
            raise PatchError(
                f"{patch.name}: original bytes do not match at "
                f"0x{patch.offset:X}\n"
                f" expected: {patch.before.hex(' ')}\n"
                f" found:    {found.hex(' ')}"
            )

        work[patch.offset:end] = patch.after
        occupied.append((patch.offset, end, patch.name))

    return bytes(work)


def atomic_replace(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def patch_file(path: Path, entry: dict, dry_run: bool) -> str:
    expected = str(entry["sha256"]).lower()
    patched_expected = str(entry.get("patched_sha256", "")).lower()
    actual = sha256_file(path).lower()

    if patched_expected and actual == patched_expected:
        print(f"[ALREADY] {path}: matches patched SHA-256")
        return "already-patched"

    if actual != expected:
        raise PatchError(
            f"Hash mismatch for {path}\n"
            f" expected original: {expected}\n"
            + (f" expected patched:  {patched_expected}\n" if patched_expected else "")
            + f" actual:            {actual}"
        )

    patches = [validate_patch(item) for item in entry.get("patches", [])]
    if not patches:
        print(f"[VERIFY] {path}: supported original, no byte patches defined")
        return "verified-only"

    original = path.read_bytes()
    patched = apply_to_bytes(original, patches)
    final_hash = sha256_bytes(patched)

    if patched_expected and final_hash != patched_expected:
        raise PatchError(
            f"Final hash mismatch for {path.name}\n"
            f" manifest patched_sha256: {patched_expected}\n"
            f" calculated:              {final_hash}"
        )

    for patch in patches:
        print(f"[PATCH] {path.name} @ 0x{patch.offset:X}: {patch.name}")

    print(f"[HASH] {path.name}: {actual} -> {final_hash}")

    if dry_run:
        print(f"[DRY-RUN] no bytes written: {path}")
        return "dry-run"

    backup = path.with_suffix(path.suffix + ".rex.bak")
    if not backup.exists():
        shutil.copy2(path, backup)
        print(f"[BACKUP] {backup}")
    elif sha256_file(backup).lower() != expected:
        raise PatchError(
            f"Existing backup is not the supported original: {backup}. "
            "Refusing to overwrite it."
        )

    atomic_replace(path, patched)
    written_hash = sha256_file(path).lower()
    if written_hash != final_hash:
        raise PatchError(
            f"Post-write verification failed for {path}: "
            f"{written_hash} != {final_hash}"
        )

    print(f"[WRITE] {path}")
    return "patched"


def main() -> int:
    parser = argparse.ArgumentParser(description="Hash-guarded ReXtreme binary patcher")
    parser.add_argument("game_dir", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("patches/1.7.3.8-x86.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--require-patches",
        action="store_true",
        help="fail if the manifest contains no active byte patches",
    )
    args = parser.parse_args()

    game_dir = args.game_dir.resolve()
    manifest_path = args.manifest.resolve()

    if not game_dir.is_dir():
        print(f"Game directory not found: {game_dir}", file=sys.stderr)
        return 2
    if not manifest_path.is_file():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    try:
        manifest = load_manifest(manifest_path)
        total_patches = sum(len(entry.get("patches", [])) for entry in manifest["files"])
        if args.require_patches and total_patches == 0:
            raise PatchError("Manifest contains no active byte patches.")

        states: list[str] = []
        for entry in manifest["files"]:
            target = game_dir / entry["path"]
            if not target.is_file():
                raise PatchError(f"Required file not found: {target}")
            states.append(patch_file(target, entry, args.dry_run))

    except (PatchError, KeyError, ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        "[DONE] "
        + ", ".join(
            f"{state}={states.count(state)}" for state in sorted(set(states))
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
