#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

MAGIC = 0x42485852  # RXHB
VERSION = 1
MAX_BINDINGS = 128
HEADER = struct.Struct("<7I")
ENTRY = struct.Struct("<4IiIiI")

ELEMENTS = {
    "position": 1,
    "speed": 2,
    "nitro": 3,
    "lap": 4,
    "timer": 5,
    "minimap": 6,
    "objective": 7,
}
PROPERTIES = {
    "x": 1,
    "y": 2,
    "scale": 3,
    "opacity": 4,
    "visible": 5,
}
BASE = {
    "module_rva": 1,
    "pointer_rva": 2,
}
VALUE = {
    "i32": 1,
    "u32": 2,
    "u8_bool": 3,
    "float_scaled": 4,
}
FLAG_VERIFIED = 1


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
        raise BindingError(f"{name}: bool is not integer")
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
    if data.get("format") != "rextreme-race-hud-bindings":
        raise BindingError("invalid format")
    if data.get("version") != VERSION:
        raise BindingError("unsupported version")
    if data.get("build") != "1.7.3.8-x86":
        raise BindingError("bindings must target 1.7.3.8-x86")
    policy = data.get("policy")
    if not isinstance(policy, dict):
        raise BindingError("policy missing")
    if policy.get("original_elements_only") is not True:
        raise BindingError("original_elements_only must remain true")
    if policy.get("create_new_hud_widgets") is not False:
        raise BindingError("create_new_hud_widgets must remain false")
    bindings = data.get("bindings")
    if not isinstance(bindings, list):
        raise BindingError("bindings must be array")
    if len(bindings) > MAX_BINDINGS:
        raise BindingError("too many bindings")
    return data


def pe_fingerprint(data: dict, non_empty: bool) -> tuple[int, int]:
    pe = data.get("pe")
    if not non_empty and pe is None:
        return 0, 0
    if not isinstance(pe, dict):
        raise BindingError("non-empty HUD bindings require PE fingerprint")
    stamp = parse_int(pe.get("time_date_stamp"), "pe.time_date_stamp")
    size = parse_int(pe.get("size_of_image"), "pe.size_of_image")
    if stamp <= 0 or size <= 0:
        raise BindingError("PE fingerprint values must be positive")
    return stamp & 0xFFFFFFFF, size & 0xFFFFFFFF


def normalize(raw: dict, seen: set[tuple[str, str]]) -> tuple[bytes, tuple[str, str]]:
    if not isinstance(raw, dict):
        raise BindingError("binding must be object")
    element = raw.get("element")
    prop = raw.get("property")
    if element not in ELEMENTS:
        raise BindingError(f"invalid element: {element!r}")
    if prop not in PROPERTIES:
        raise BindingError(f"invalid property: {prop!r}")
    key = (element, prop)
    if key in seen:
        raise BindingError(f"duplicate HUD binding: {element}.{prop}")
    seen.add(key)

    if raw.get("verified") is not True:
        raise BindingError(f"{element}.{prop}: verified must be true")
    evidence = raw.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise BindingError(f"{element}.{prop}: evidence required")

    base = raw.get("base")
    if base not in BASE:
        raise BindingError(f"{element}.{prop}: invalid base")
    rva = parse_int(raw.get("target_rva"), f"{element}.{prop}.target_rva")
    if rva <= 0:
        raise BindingError(f"{element}.{prop}: target_rva must be positive")

    field_offset = parse_int(raw.get("field_offset", 0), f"{element}.{prop}.field_offset")
    value_kind = raw.get("value_kind")
    if value_kind not in VALUE:
        raise BindingError(f"{element}.{prop}: invalid value_kind")
    scale = parse_int(raw.get("scale_divisor", 1), f"{element}.{prop}.scale_divisor")
    if value_kind == "float_scaled":
        if scale <= 0:
            raise BindingError(f"{element}.{prop}: float_scaled requires positive scale")
    elif scale != 1:
        raise BindingError(f"{element}.{prop}: non-float scale must be 1")

    if prop == "visible":
        if value_kind not in {"u8_bool", "i32", "u32"}:
            raise BindingError(f"{element}.{prop}: visible requires bool/integer target")
    elif value_kind == "u8_bool":
        raise BindingError(f"{element}.{prop}: numeric property cannot use u8_bool")

    return ENTRY.pack(
        ELEMENTS[element],
        PROPERTIES[prop],
        BASE[base],
        rva & 0xFFFFFFFF,
        field_offset,
        VALUE[value_kind],
        scale,
        FLAG_VERIFIED,
    ), key


def build(source: Path, output: Path, report: Path | None = None) -> dict:
    data = load_source(source)
    seen: set[tuple[str, str]] = set()
    packed: list[bytes] = []
    names: list[str] = []
    for raw in data["bindings"]:
        item, key = normalize(raw, seen)
        packed.append(item)
        names.append(f"{key[0]}.{key[1]}")

    stamp, size = pe_fingerprint(data, bool(packed))
    payload = b"".join(packed)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(HEADER.pack(
        MAGIC, VERSION, len(packed), ENTRY.size, fnv1a(payload), stamp, size
    ) + payload)

    summary = {
        "format": "rextreme-race-hud-runtime-catalog",
        "version": VERSION,
        "build": "1.7.3.8-x86",
        "count": len(packed),
        "entry_size": ENTRY.size,
        "safe_empty_catalog": len(packed) == 0,
        "original_elements_only": True,
        "create_new_hud_widgets": False,
        "bindings": names,
        "output": str(output),
    }
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Build verified original race HUD binding catalog")
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--report", type=Path)
    ns = ap.parse_args()
    try:
        result = build(ns.source, ns.output, ns.report)
    except (OSError, json.JSONDecodeError, BindingError, ValueError, struct.error) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
