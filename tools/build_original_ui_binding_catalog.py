#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

MAGIC = 0x55495852  # RXIU
VERSION = 1
MAX_BINDINGS = 128

HEADER = struct.Struct("<7I")
ENTRY = struct.Struct("<32sIIiII")

KIND = {
    "screen": 1,
    "panel": 2,
    "button": 3,
    "slider": 4,
    "toggle": 5,
    "label": 6,
    "popup": 7,
    "list": 8,
    "tab": 9,
    "sound": 10,
    "animation": 11,
}
BASE = {
    "module_rva": 1,
    "pointer_rva": 2,
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
    if data.get("format") != "rextreme-original-ui-bindings":
        raise BindingError("invalid format")
    if data.get("version") != VERSION:
        raise BindingError("unsupported version")
    if data.get("build") != "1.7.3.8-x86":
        raise BindingError("bindings must target 1.7.3.8-x86")

    policy = data.get("policy")
    if not isinstance(policy, dict):
        raise BindingError("policy missing")
    if policy.get("original_ui_only") is not True:
        raise BindingError("original_ui_only must remain true")
    if policy.get("custom_ui_assets_allowed") is not False:
        raise BindingError("custom_ui_assets_allowed must remain false")
    if policy.get("fallback_if_unmapped") != "feature-hidden":
        raise BindingError("fallback_if_unmapped must be feature-hidden")

    bindings = data.get("bindings")
    if not isinstance(bindings, list):
        raise BindingError("bindings must be an array")
    if len(bindings) > MAX_BINDINGS:
        raise BindingError("too many UI bindings")
    return data


def pe_fingerprint(source: dict, non_empty: bool) -> tuple[int, int]:
    pe = source.get("pe")
    if not non_empty and pe is None:
        return 0, 0
    if not isinstance(pe, dict):
        raise BindingError("non-empty UI bindings require exact PE fingerprint")
    ts = parse_int(pe.get("time_date_stamp"), "pe.time_date_stamp")
    size = parse_int(pe.get("size_of_image"), "pe.size_of_image")
    if ts <= 0 or size <= 0:
        raise BindingError("PE fingerprint values must be positive")
    return ts & 0xFFFFFFFF, size & 0xFFFFFFFF


def normalize(raw: dict, ids: set[str]) -> bytes:
    if not isinstance(raw, dict):
        raise BindingError("binding must be object")
    ident = raw.get("id")
    if not isinstance(ident, str) or not ident or len(ident.encode("ascii", "strict")) >= 32:
        raise BindingError("binding id must be non-empty ASCII <32 bytes")
    if ident in ids:
        raise BindingError(f"duplicate id: {ident}")
    ids.add(ident)

    if raw.get("verified") is not True:
        raise BindingError(f"{ident}: verified must be true")
    evidence = raw.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise BindingError(f"{ident}: evidence is required")

    kind_name = raw.get("kind")
    if kind_name not in KIND:
        raise BindingError(f"{ident}: invalid kind")
    base_name = raw.get("base")
    if base_name not in BASE:
        raise BindingError(f"{ident}: invalid base")

    rva = parse_int(raw.get("target_rva"), f"{ident}.target_rva")
    offset = parse_int(raw.get("field_offset", 0), f"{ident}.field_offset")
    semantic = parse_int(raw.get("semantic", 0), f"{ident}.semantic")
    if rva <= 0:
        raise BindingError(f"{ident}: target_rva must be positive")

    ident_bytes = ident.encode("ascii") + b"\0"
    ident_bytes = ident_bytes.ljust(32, b"\0")
    return ENTRY.pack(
        ident_bytes,
        KIND[kind_name],
        BASE[base_name],
        offset,
        rva & 0xFFFFFFFF,
        semantic & 0xFFFFFFFF,
    )


def build(source: Path, output: Path, report: Path | None = None) -> dict:
    data = load_source(source)
    ids: set[str] = set()
    entries = [normalize(x, ids) for x in data["bindings"]]
    ts, size = pe_fingerprint(data, bool(entries))
    payload = b"".join(entries)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(HEADER.pack(
        MAGIC, VERSION, len(entries), ENTRY.size, fnv1a(payload), ts, size
    ) + payload)

    summary = {
        "format": "rextreme-original-ui-runtime-catalog",
        "version": VERSION,
        "build": "1.7.3.8-x86",
        "count": len(entries),
        "safe_empty_catalog": len(entries) == 0,
        "original_ui_only": True,
        "custom_ui_assets_allowed": False,
        "fallback_if_unmapped": "feature-hidden",
        "output": str(output),
    }
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Build verified original Asphalt Xtreme UI binding catalog")
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--report", type=Path)
    ns = ap.parse_args()
    try:
        result = build(ns.source, ns.output, ns.report)
    except (OSError, UnicodeError, json.JSONDecodeError, BindingError, struct.error) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
