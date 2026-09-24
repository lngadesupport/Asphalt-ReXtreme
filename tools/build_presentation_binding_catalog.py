#!/usr/bin/env python3
"""Build verified runtime bindings for ReXtreme presentation capabilities."""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

MAGIC = 0x42505852  # RXPB
VERSION = 1
MAX_ENTRIES = 64
ID_BYTES = 32
HEADER = struct.Struct("<IIIII")
ENTRY = struct.Struct("<32sIIiIiI")

BASE_KINDS = {
    "module_rva": 1,
    "pointer_rva": 2,
}
VALUE_KINDS = {
    "i32": 1,
    "u32": 2,
    "u8_bool": 3,
    "float_scaled": 4,
}
FLAG_VERIFIED = 1 << 0


class BindingCatalogError(RuntimeError):
    pass


def fnv1a(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def parse_int(value, name: str) -> int:
    if isinstance(value, bool):
        raise BindingCatalogError(f"{name}: bool is not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise BindingCatalogError(f"{name}: invalid integer {value!r}") from exc
    raise BindingCatalogError(f"{name}: expected integer or 0x string")


def load_capabilities(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "rextreme-presentation-capabilities":
        raise BindingCatalogError("invalid presentation capability source format")
    if data.get("version") != 1 or data.get("build") != "1.7.3.8-x86":
        raise BindingCatalogError("capability source must be version 1 for 1.7.3.8-x86")
    caps = data.get("capabilities")
    if not isinstance(caps, list):
        raise BindingCatalogError("capabilities must be an array")

    out: dict[str, dict] = {}
    for cap in caps:
        if not isinstance(cap, dict):
            raise BindingCatalogError("capability must be an object")
        cid = cap.get("id")
        if not isinstance(cid, str) or not cid:
            raise BindingCatalogError("capability id missing")
        if cap.get("verified") is not True:
            continue
        out[cid] = cap
    return out


def load_source(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "rextreme-presentation-bindings":
        raise BindingCatalogError("invalid binding source format")
    if data.get("version") != VERSION:
        raise BindingCatalogError("unsupported binding source version")
    if data.get("build") != "1.7.3.8-x86":
        raise BindingCatalogError("binding source must target 1.7.3.8-x86")
    bindings = data.get("bindings")
    if not isinstance(bindings, list):
        raise BindingCatalogError("bindings must be an array")
    if len(bindings) > MAX_ENTRIES:
        raise BindingCatalogError(f"too many bindings: {len(bindings)} > {MAX_ENTRIES}")
    return data


def normalize(raw: dict, capabilities: dict[str, dict], seen: set[str]) -> tuple:
    if not isinstance(raw, dict):
        raise BindingCatalogError("binding must be an object")

    bid = raw.get("id")
    if not isinstance(bid, str) or not bid:
        raise BindingCatalogError("binding id missing")
    if bid in seen:
        raise BindingCatalogError(f"duplicate binding id: {bid}")
    seen.add(bid)

    try:
        encoded = bid.encode("ascii")
    except UnicodeEncodeError as exc:
        raise BindingCatalogError(f"{bid}: id must be ASCII") from exc
    if len(encoded) >= ID_BYTES:
        raise BindingCatalogError(f"{bid}: id exceeds {ID_BYTES - 1} bytes")

    capability = capabilities.get(bid)
    if capability is None:
        raise BindingCatalogError(f"{bid}: no verified capability with the same id")

    if raw.get("verified") is not True:
        raise BindingCatalogError(f"{bid}: verified must be true")
    evidence = raw.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise BindingCatalogError(f"{bid}: non-empty evidence is required")

    base_name = raw.get("base_kind")
    value_name = raw.get("value_kind")
    if base_name not in BASE_KINDS:
        raise BindingCatalogError(f"{bid}: invalid base_kind")
    if value_name not in VALUE_KINDS:
        raise BindingCatalogError(f"{bid}: invalid value_kind")

    target_rva = parse_int(raw.get("target_rva"), f"{bid}.target_rva")
    field_offset = parse_int(raw.get("field_offset", 0), f"{bid}.field_offset")
    scale_divisor = parse_int(raw.get("scale_divisor", 1), f"{bid}.scale_divisor")

    if not 0 < target_rva <= 0xFFFFFFFF:
        raise BindingCatalogError(f"{bid}: target_rva must be within PE32 RVA range")
    if not -0x80000000 <= field_offset <= 0x7FFFFFFF:
        raise BindingCatalogError(f"{bid}: field_offset outside int32")
    if value_name == "float_scaled":
        if scale_divisor <= 0:
            raise BindingCatalogError(f"{bid}: float_scaled requires scale_divisor > 0")
    elif scale_divisor != 1:
        raise BindingCatalogError(f"{bid}: non-float binding requires scale_divisor=1")

    if value_name == "u8_bool":
        minimum = int(capability.get("minimum", 0))
        maximum = int(capability.get("maximum", 1))
        if (minimum, maximum) != (0, 1):
            raise BindingCatalogError(f"{bid}: u8_bool capability must use 0..1 range")

    ident = encoded + b"\0" * (ID_BYTES - len(encoded))
    return (
        ident,
        BASE_KINDS[base_name],
        target_rva,
        field_offset,
        VALUE_KINDS[value_name],
        scale_divisor,
        FLAG_VERIFIED,
    )


def build(source: Path, capability_source: Path, output: Path, report: Path | None = None) -> dict:
    data = load_source(source)
    capabilities = load_capabilities(capability_source)
    seen: set[str] = set()
    packed: list[bytes] = []
    ids: list[str] = []

    for raw in data["bindings"]:
        values = normalize(raw, capabilities, seen)
        packed.append(ENTRY.pack(*values))
        ids.append(raw["id"])

    body = b"".join(packed)
    payload = HEADER.pack(MAGIC, VERSION, len(packed), ENTRY.size, fnv1a(body)) + body

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)

    summary = {
        "format": "rextreme-presentation-binding-runtime-catalog",
        "version": VERSION,
        "build": "1.7.3.8-x86",
        "count": len(packed),
        "entry_size": ENTRY.size,
        "output": str(output),
        "binding_ids": ids,
        "safe_empty_catalog": len(packed) == 0,
    }
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Build verified ReXtreme presentation bindings")
    ap.add_argument("source", type=Path)
    ap.add_argument("capabilities", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--report", type=Path)
    ns = ap.parse_args()

    try:
        summary = build(ns.source, ns.capabilities, ns.output, ns.report)
    except (OSError, json.JSONDecodeError, BindingCatalogError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
