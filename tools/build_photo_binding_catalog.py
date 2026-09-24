#!/usr/bin/env python3
"""Build verified Photo Mode camera/HUD binding catalog."""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

MAGIC = 0x48505852  # RXPH
VERSION = 1
MAX_ENTRIES = 32
HEADER = struct.Struct("<IIIII")
ENTRY = struct.Struct("<IIIiIiI")

SEMANTICS = {
    "position_x": 1,
    "position_y": 2,
    "position_z": 3,
    "pitch": 4,
    "yaw": 5,
    "roll": 6,
    "fov": 7,
    "hud_visible": 8,
}
BASE_KINDS = {"module_rva": 1, "pointer_rva": 2}
VALUE_KINDS = {"i32": 1, "u32": 2, "u8_bool": 3, "float_scaled": 4}
FLAG_VERIFIED = 1


class PhotoBindingError(RuntimeError):
    pass


def fnv1a(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def parse_int(value, name: str) -> int:
    if isinstance(value, bool):
        raise PhotoBindingError(f"{name}: bool is not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise PhotoBindingError(f"{name}: invalid integer {value!r}") from exc
    raise PhotoBindingError(f"{name}: expected integer or 0x string")


def load_source(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "rextreme-photo-bindings":
        raise PhotoBindingError("invalid source format")
    if data.get("version") != VERSION or data.get("build") != "1.7.3.8-x86":
        raise PhotoBindingError("source must target 1.7.3.8-x86 version 1")
    bindings = data.get("bindings")
    if not isinstance(bindings, list):
        raise PhotoBindingError("bindings must be an array")
    if len(bindings) > MAX_ENTRIES:
        raise PhotoBindingError(f"too many bindings: {len(bindings)}")
    return data


def normalize(raw: dict, seen: set[int]) -> tuple:
    if not isinstance(raw, dict):
        raise PhotoBindingError("binding must be an object")

    semantic_name = raw.get("semantic")
    if semantic_name not in SEMANTICS:
        raise PhotoBindingError(f"invalid semantic: {semantic_name!r}")
    semantic = SEMANTICS[semantic_name]
    if semantic in seen:
        raise PhotoBindingError(f"duplicate semantic: {semantic_name}")
    seen.add(semantic)

    if raw.get("verified") is not True:
        raise PhotoBindingError(f"{semantic_name}: verified must be true")
    evidence = raw.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise PhotoBindingError(f"{semantic_name}: evidence is required")

    base_name = raw.get("base_kind")
    value_name = raw.get("value_kind")
    if base_name not in BASE_KINDS:
        raise PhotoBindingError(f"{semantic_name}: invalid base_kind")
    if value_name not in VALUE_KINDS:
        raise PhotoBindingError(f"{semantic_name}: invalid value_kind")

    target_rva = parse_int(raw.get("target_rva"), f"{semantic_name}.target_rva")
    field_offset = parse_int(raw.get("field_offset", 0), f"{semantic_name}.field_offset")
    divisor = parse_int(raw.get("scale_divisor", 1), f"{semantic_name}.scale_divisor")

    if not 0 < target_rva <= 0xFFFFFFFF:
        raise PhotoBindingError(f"{semantic_name}: target_rva outside PE32 RVA range")
    if not -0x80000000 <= field_offset <= 0x7FFFFFFF:
        raise PhotoBindingError(f"{semantic_name}: field_offset outside int32")

    if value_name == "float_scaled":
        if divisor <= 0:
            raise PhotoBindingError(f"{semantic_name}: float_scaled needs scale_divisor > 0")
    elif divisor != 1:
        raise PhotoBindingError(f"{semantic_name}: non-float binding needs scale_divisor=1")

    if semantic_name == "hud_visible" and value_name != "u8_bool":
        raise PhotoBindingError("hud_visible must use u8_bool")

    return (
        semantic,
        BASE_KINDS[base_name],
        target_rva,
        field_offset,
        VALUE_KINDS[value_name],
        divisor,
        FLAG_VERIFIED,
    )


def build(source: Path, output: Path, report: Path | None = None) -> dict:
    data = load_source(source)
    seen: set[int] = set()
    packed: list[bytes] = []
    semantics: list[str] = []

    for raw in data["bindings"]:
        packed.append(ENTRY.pack(*normalize(raw, seen)))
        semantics.append(raw["semantic"])

    body = b"".join(packed)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(HEADER.pack(MAGIC, VERSION, len(packed), ENTRY.size, fnv1a(body)) + body)

    required = {"position_x", "position_y", "position_z", "pitch", "yaw", "roll", "hud_visible"}
    summary = {
        "format": "rextreme-photo-binding-runtime-catalog",
        "version": VERSION,
        "build": "1.7.3.8-x86",
        "count": len(packed),
        "entry_size": ENTRY.size,
        "binding_semantics": semantics,
        "free_camera_ready": required.issubset(set(semantics)),
        "safe_empty_catalog": len(packed) == 0,
        "output": str(output),
    }
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Build verified ReXtreme Photo camera/HUD bindings")
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--report", type=Path)
    ns = ap.parse_args()

    try:
        result = build(ns.source, ns.output, ns.report)
    except (OSError, json.JSONDecodeError, PhotoBindingError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
