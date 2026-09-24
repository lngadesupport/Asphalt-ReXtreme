#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

MAGIC = 0x4D555852
VERSION = 1
MAX = 1024
HEADER = struct.Struct("<4I")
ENTRY = struct.Struct("<4i")
KIND = {"upgrade": 1, "prokit": 2}


def fnv1a(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def normalize(rows):
    out = []
    seen = set()
    for row in rows:
        ui_id = int(row["ui_action_id"])
        kind_name = str(row["kind"]).lower()
        slot = int(row["part_slot"])
        flags = int(row.get("flags", 0))

        if ui_id <= 0 or slot < 0:
            raise ValueError("ui_action_id must be positive and part_slot non-negative")
        if kind_name not in KIND:
            raise ValueError(f"invalid kind {kind_name!r}")
        if ui_id in seen:
            raise ValueError(f"duplicate ui_action_id {ui_id}")
        seen.add(ui_id)
        out.append((ui_id, KIND[kind_name], slot, flags))

    out.sort(key=lambda x: x[0])
    if len(out) > MAX:
        raise ValueError(f"too many entries: {len(out)} > {MAX}")
    return out


def build(entries):
    body = bytearray(HEADER.pack(MAGIC, VERSION, len(entries), 0))
    for row in entries:
        body += ENTRY.pack(*row)
    body += ENTRY.pack(0, 0, 0, 0) * (MAX - len(entries))
    body += struct.pack("<I", fnv1a(body))
    return bytes(body)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build CampaignUpgradeUiMap.dat")
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ns = ap.parse_args()

    obj = json.loads(ns.input.read_text(encoding="utf-8-sig"))
    rows = obj["entries"] if isinstance(obj, dict) else obj
    data = build(normalize(rows))
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_bytes(data)
    print(f"CampaignUpgradeUiMap.dat: {len(rows)} entries, {len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
