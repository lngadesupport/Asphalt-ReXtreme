#!/usr/bin/env python3
"""Build the verified ReXtreme Replay transform binding catalog.

The source JSON is intentionally review-only. Empty bindings are valid and
produce a fail-closed runtime catalog. Non-empty entries require explicit
evidence and a PE fingerprint for the exact 1.7.3.8 x86 executable.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

MAGIC = 0x42525852  # RXRB
VERSION = 1
MAX_BINDINGS = 32
CHAIN_MAX = 4

HEADER = struct.Struct("<7I")
ENTRY = struct.Struct("<4I4iiIiI")

SEMANTICS = {
    "time_ms": 1,
    "entity_id": 2,
    "position_x": 3,
    "position_y": 4,
    "position_z": 5,
    "rotation_x": 6,
    "rotation_y": 7,
    "rotation_z": 8,
    "rotation_w": 9,
    "velocity_x": 10,
    "velocity_y": 11,
    "velocity_z": 12,
    "state_flags": 13,
}
REQUIRED = {
    "time_ms", "entity_id",
    "position_x", "position_y", "position_z",
    "rotation_x", "rotation_y", "rotation_z", "rotation_w",
}
ROOT_KINDS = {
    "gui_argument": 1,
    "module_rva": 2,
    "pointer_rva": 3,
}
VALUE_KINDS = {
    "i32": 1,
    "u32": 2,
    "u8_bool": 3,
    "float_scaled": 4,
}
FLAG_VERIFIED = 1 << 0
FLAG_OPTIONAL = 1 << 1


class BindingError(RuntimeError):
    pass


def fnv1a(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def parse_int(value, name: str) -> int:
    if isinstance(value, bool):
        raise BindingError(f"{name}: bool is not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise BindingError(f"{name}: invalid integer {value!r}") from exc
    raise BindingError(f"{name}: expected integer or 0x string")


def load_source(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "rextreme-replay-bindings":
        raise BindingError("invalid format")
    if data.get("version") != 1:
        raise BindingError("unsupported source version")
    if data.get("build") != "1.7.3.8-x86":
        raise BindingError("bindings must target 1.7.3.8-x86")
    bindings = data.get("bindings")
    if not isinstance(bindings, list):
        raise BindingError("bindings must be an array")
    if len(bindings) > MAX_BINDINGS:
        raise BindingError(f"too many bindings: {len(bindings)} > {MAX_BINDINGS}")
    return data


def parse_pe_fingerprint(source: dict, non_empty: bool) -> tuple[int, int]:
    pe = source.get("pe")
    if not non_empty:
        if pe is None:
            return 0, 0
    if not isinstance(pe, dict):
        raise BindingError("non-empty bindings require pe fingerprint")
    timestamp = parse_int(pe.get("time_date_stamp"), "pe.time_date_stamp")
    size = parse_int(pe.get("size_of_image"), "pe.size_of_image")
    if timestamp <= 0 or size <= 0:
        raise BindingError("PE fingerprint values must be positive")
    return timestamp & 0xFFFFFFFF, size & 0xFFFFFFFF


def normalize(raw: dict, seen: set[str]) -> tuple[bytes, str]:
    if not isinstance(raw, dict):
        raise BindingError("binding entry must be an object")

    semantic_name = raw.get("semantic")
    if semantic_name not in SEMANTICS:
        raise BindingError(f"unknown semantic: {semantic_name!r}")
    if semantic_name in seen:
        raise BindingError(f"duplicate semantic: {semantic_name}")
    seen.add(semantic_name)

    if raw.get("verified") is not True:
        raise BindingError(f"{semantic_name}: verified must be true")
    evidence = raw.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise BindingError(f"{semantic_name}: non-empty evidence is required")

    root_name = raw.get("root")
    if root_name not in ROOT_KINDS:
        raise BindingError(f"{semantic_name}: invalid root {root_name!r}")
    root_kind = ROOT_KINDS[root_name]
    root_rva = parse_int(raw.get("root_rva", 0), f"{semantic_name}.root_rva")
    if root_name == "gui_argument":
        if root_rva != 0:
            raise BindingError(f"{semantic_name}: gui_argument root_rva must be 0")
    elif root_rva <= 0:
        raise BindingError(f"{semantic_name}: module/pointer root requires positive root_rva")

    chain = raw.get("chain", [])
    if not isinstance(chain, list) or len(chain) > CHAIN_MAX:
        raise BindingError(f"{semantic_name}: chain must contain at most {CHAIN_MAX} offsets")
    chain_offsets = [parse_int(v, f"{semantic_name}.chain") for v in chain]
    chain_offsets.extend([0] * (CHAIN_MAX - len(chain_offsets)))

    field_offset = parse_int(raw.get("field_offset", 0), f"{semantic_name}.field_offset")

    value_name = raw.get("value_kind")
    if value_name not in VALUE_KINDS:
        raise BindingError(f"{semantic_name}: invalid value_kind {value_name!r}")
    value_kind = VALUE_KINDS[value_name]
    scale = parse_int(raw.get("scale_divisor", 1), f"{semantic_name}.scale_divisor")
    if value_name == "float_scaled":
        if scale <= 0:
            raise BindingError(f"{semantic_name}: float_scaled requires positive scale_divisor")
    elif scale != 1:
        raise BindingError(f"{semantic_name}: non-float binding scale_divisor must be 1")

    optional = bool(raw.get("optional", False))
    if semantic_name in REQUIRED and optional:
        raise BindingError(f"{semantic_name}: required Replay semantic cannot be optional")

    flags = FLAG_VERIFIED | (FLAG_OPTIONAL if optional else 0)

    packed = ENTRY.pack(
        SEMANTICS[semantic_name],
        root_kind,
        root_rva & 0xFFFFFFFF,
        len(chain),
        *chain_offsets,
        field_offset,
        value_kind,
        scale,
        flags,
    )
    return packed, semantic_name


def build(source: Path, output: Path, report: Path | None = None) -> dict:
    data = load_source(source)
    seen: set[str] = set()
    entries: list[bytes] = []
    names: list[str] = []

    for raw in data["bindings"]:
        packed, name = normalize(raw, seen)
        entries.append(packed)
        names.append(name)

    pe_timestamp, pe_size = parse_pe_fingerprint(data, bool(entries))
    payload_entries = b"".join(entries)
    header = HEADER.pack(
        MAGIC,
        VERSION,
        len(entries),
        ENTRY.size,
        fnv1a(payload_entries),
        pe_timestamp,
        pe_size,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(header + payload_entries)

    ready = REQUIRED.issubset(seen)
    summary = {
        "format": "rextreme-replay-binding-runtime-catalog",
        "version": VERSION,
        "build": "1.7.3.8-x86",
        "count": len(entries),
        "entry_size": ENTRY.size,
        "safe_empty_catalog": len(entries) == 0,
        "recording_ready": ready,
        "binding_semantics": names,
        "pe_time_date_stamp": pe_timestamp,
        "pe_size_of_image": pe_size,
        "output": str(output),
    }
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Build verified Replay transform binding catalog")
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--report", type=Path)
    ns = ap.parse_args()

    try:
        summary = build(ns.source, ns.output, ns.report)
    except (OSError, json.JSONDecodeError, BindingError, ValueError, struct.error) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
