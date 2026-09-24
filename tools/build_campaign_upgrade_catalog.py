#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import struct
from pathlib import Path

MAGIC = 0x55435852
VERSION = 2
MAX = 16384
HEADER = struct.Struct("<4I")
ENTRY = struct.Struct("<10i")

KIND = {"upgrade": 1, "prokit": 2}
COST = {"credits": 1, "premium": 2, "inventory": 3, "free": 4}


def fnv1a(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def parse_int(v, default=0):
    if v in (None, ""):
        return default
    return int(v)


def read_rows(path: Path):
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(obj, dict) and "entries" in obj:
        return obj["entries"]
    if isinstance(obj, list):
        return obj
    raise ValueError("JSON must be an array or contain entries[]")


def normalize(rows):
    out = []
    seen = set()

    for row in rows:
        car = parse_int(row.get("car_id"))
        kind_name = str(row.get("kind", "")).strip().lower()
        cost_name = str(row.get("cost_type", "")).strip().lower()
        slot = parse_int(row.get("part_slot"))
        level = parse_int(row.get("target_level"))
        item = parse_int(row.get("item_id"))
        cost = parse_int(row.get("cost"))
        unlock = parse_int(row.get("unlock_node_id"))
        flags = parse_int(row.get("flags"))

        if car <= 0 or slot < 0 or level <= 0:
            raise ValueError("invalid car/slot/target level")
        if kind_name not in KIND:
            raise ValueError(f"invalid kind {kind_name!r}")
        if cost_name not in COST:
            raise ValueError(f"invalid cost_type {cost_name!r}")
        if cost < 0 or unlock < 0:
            raise ValueError("negative cost/unlock node")
        if cost_name == "inventory" and item <= 0:
            raise ValueError("inventory cost requires item_id")
        if cost_name != "inventory" and item != 0:
            raise ValueError("item_id must be zero unless cost_type=inventory")

        key = (car, KIND[kind_name], slot, level)
        if key in seen:
            raise ValueError(f"duplicate upgrade key {key}")
        seen.add(key)

        out.append((
            car, KIND[kind_name], slot, level,
            COST[cost_name], item, cost, unlock, flags, 0
        ))

    out.sort(key=lambda x: x[:4])
    if len(out) > MAX:
        raise ValueError(f"too many entries: {len(out)} > {MAX}")
    return out


def build(entries):
    body = bytearray(HEADER.pack(MAGIC, VERSION, len(entries), 0))
    for row in entries:
        body += ENTRY.pack(*row)
    body += ENTRY.pack(*([0] * 10)) * (MAX - len(entries))
    body += struct.pack("<I", fnv1a(body))
    return bytes(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=Path("CampaignUpgrades.dat"))
    ns = ap.parse_args()

    entries = normalize(read_rows(ns.input))
    data = build(entries)
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_bytes(data)
    print(f"CampaignUpgrades.dat: {len(entries)} entries, {len(data)} bytes")


if __name__ == "__main__":
    main()
