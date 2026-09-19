#!/usr/bin/env python3
"""
Asphalt ReXtreme patcher core.

This tool applies only explicitly defined, hash-verified byte patches.
It never guesses offsets and refuses to patch an unknown build.

Manifest format:
{
  "build": {...},
  "files": [
    {
      "path": "AMS.exe",
      "sha256": "...",
      "patches": [
        {
          "name": "example",
          "offset": 1234,
          "before": "75 0A",
          "after":  "90 90"
        }
      ]
    }
  ]
}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


class PatchError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_hex(s: str) -> bytes:
    compact = "".join(s.split())
    if len(compact) % 2:
        raise PatchError(f"Invalid hex string length: {s!r}")
    try:
        return bytes.fromhex(compact)
    except ValueError as exc:
        raise PatchError(f"Invalid hex string: {s!r}") from exc


@dataclass
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


def validate_patch(p: dict) -> BytePatch:
    name = str(p.get("name", "unnamed patch"))
    offset = int(p["offset"])
    before = parse_hex(p["before"])
    after = parse_hex(p["after"])
    if offset < 0:
        raise PatchError(f"{name}: negative offset")
    if len(before) != len(after):
        raise PatchError(f"{name}: before/after sizes differ")
    return BytePatch(name, offset, before, after)


def apply_file_patches(path: Path, entry: dict, dry_run: bool) -> None:
    expected_hash = str(entry["sha256"]).lower()
    actual_hash = sha256_file(path).lower()
    if actual_hash != expected_hash:
        raise PatchError(
            f"Hash mismatch for {path.name}\n"
            f" expected: {expected_hash}\n"
            f" actual:   {actual_hash}"
        )

    patches = [validate_patch(p) for p in entry.get("patches", [])]
    if not patches:
        print(f"[OK] {path}: verified, no patches defined")
        return

    data = bytearray(path.read_bytes())

    for p in patches:
        end = p.offset + len(p.before)
        if end > len(data):
            raise PatchError(f"{p.name}: offset outside file")
        found = bytes(data[p.offset:end])
        if found != p.before:
            raise PatchError(
                f"{p.name}: original bytes do not match at 0x{p.offset:X}\n"
                f" expected: {p.before.hex(' ')}\n"
                f" found:    {found.hex(' ')}"
            )
        print(f"[PATCH] {path.name} @ 0x{p.offset:X}: {p.name}")
        if not dry_run:
            data[p.offset:end] = p.after

    if not dry_run:
        backup = path.with_suffix(path.suffix + ".rex.bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_bytes(data)
        print(f"[WRITE] {path}")
        print(f"[BACKUP] {backup}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game_dir", type=Path)
    ap.add_argument("--manifest", type=Path, default=Path("patches/1.7.3.8-x86.json"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

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
        for entry in manifest["files"]:
            target = game_dir / entry["path"]
            if not target.is_file():
                raise PatchError(f"Required file not found: {target}")
            apply_file_patches(target, entry, args.dry_run)
    except (PatchError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
