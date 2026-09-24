#!/usr/bin/env python3
"""Build the runtime allowlist for ReXtreme presentation options.

The input is manually reviewed/verified data. Candidate-only audit results are
not accepted here. An empty list is valid and intentionally means the game
exposes no additional renderer/camera options yet.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

MAGIC = 0x43505852  # RXPC
VERSION = 1
MAX_ENTRIES = 64
ID_BYTES = 32
ENTRY = struct.Struct("<32sIiiiiI")
HEADER = struct.Struct("<IIII")

KINDS = {
    "toggle": 1,
    "choice": 2,
    "slider": 3,
}

FLAG_VERIFIED = 1 << 0
FLAG_RESTART_REQUIRED = 1 << 1


class CatalogError(RuntimeError):
    pass


def load_verified(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "rextreme-presentation-capabilities":
        raise CatalogError("invalid format")
    if data.get("version") != 1:
        raise CatalogError("unsupported catalog source version")
    if data.get("build") != "1.7.3.8-x86":
        raise CatalogError("capability source must target build 1.7.3.8-x86")
    caps = data.get("capabilities")
    if not isinstance(caps, list):
        raise CatalogError("capabilities must be an array")
    if len(caps) > MAX_ENTRIES:
        raise CatalogError(f"too many capabilities: {len(caps)} > {MAX_ENTRIES}")
    return data


def normalize_entry(raw: dict, seen: set[str]) -> tuple:
    if not isinstance(raw, dict):
        raise CatalogError("capability entry must be an object")

    cap_id = raw.get("id")
    if not isinstance(cap_id, str) or not cap_id:
        raise CatalogError("capability id is required")
    try:
        encoded = cap_id.encode("ascii")
    except UnicodeEncodeError as exc:
        raise CatalogError(f"{cap_id!r}: id must be ASCII") from exc
    if len(encoded) >= ID_BYTES:
        raise CatalogError(f"{cap_id!r}: id must fit in {ID_BYTES - 1} bytes")
    if cap_id in seen:
        raise CatalogError(f"duplicate capability id: {cap_id}")
    seen.add(cap_id)

    if raw.get("verified") is not True:
        raise CatalogError(f"{cap_id}: verified must be true")

    evidence = raw.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise CatalogError(f"{cap_id}: at least one verified evidence reference is required")

    kind_name = raw.get("kind")
    if kind_name not in KINDS:
        raise CatalogError(f"{cap_id}: kind must be toggle, choice or slider")
    kind = KINDS[kind_name]

    minimum = int(raw.get("minimum", 0))
    maximum = int(raw.get("maximum", 1 if kind == KINDS["toggle"] else 0))
    step = int(raw.get("step", 1))
    original = int(raw.get("original_value", minimum))

    if minimum > maximum:
        raise CatalogError(f"{cap_id}: minimum > maximum")
    if step < 0:
        raise CatalogError(f"{cap_id}: step must be >= 0")
    if not minimum <= original <= maximum:
        raise CatalogError(f"{cap_id}: original_value outside range")
    if kind == KINDS["toggle"] and (minimum, maximum) != (0, 1):
        raise CatalogError(f"{cap_id}: toggle range must be 0..1")

    flags = FLAG_VERIFIED
    if raw.get("restart_required") is True:
        flags |= FLAG_RESTART_REQUIRED

    ident = encoded + b"\0" * (ID_BYTES - len(encoded))
    return ident, kind, minimum, maximum, step, original, flags


def build(source: Path, output: Path, report: Path | None = None) -> dict:
    data = load_verified(source)
    seen: set[str] = set()
    packed_entries: list[bytes] = []
    ids: list[str] = []

    for raw in data["capabilities"]:
        values = normalize_entry(raw, seen)
        packed_entries.append(ENTRY.pack(*values))
        ids.append(raw["id"])

    payload = HEADER.pack(MAGIC, VERSION, len(packed_entries), ENTRY.size)
    payload += b"".join(packed_entries)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)

    summary = {
        "format": "rextreme-presentation-runtime-catalog",
        "version": VERSION,
        "build": data["build"],
        "count": len(packed_entries),
        "entry_size": ENTRY.size,
        "output": str(output),
        "capability_ids": ids,
        "safe_empty_catalog": len(packed_entries) == 0,
    }

    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Build verified ReXtreme presentation capability catalog")
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    try:
        summary = build(args.source, args.output, args.report)
    except (OSError, json.JSONDecodeError, CatalogError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
