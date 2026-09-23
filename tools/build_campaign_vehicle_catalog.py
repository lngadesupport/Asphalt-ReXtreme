#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import struct
from pathlib import Path

MAGIC = 0x54435852
VERSION = 1
MAX = 256

TYPE = {
    "blueprint": 1,
    "credits": 2,
    "premium": 3,
    "free": 4,
}

ENTRY = struct.Struct("<8i")
HEADER = struct.Struct("<4I")


def fnv1a(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def read_json(path: Path):
    obj = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(obj, dict) and "vehicles" in obj:
        return obj["vehicles"]
    if isinstance(obj, list):
        return obj
    raise ValueError("JSON must be an array or contain vehicles[]")


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_int(v, default=0):
    if v in (None, ""):
        return default
    return int(v)


def normalize(rows):
    out = []
    seen = set()

    for row in rows:
        car = parse_int(row.get("car_id"))
        kind = str(row.get("acquisition_type", "")).strip().lower()
        if car <= 0:
            raise ValueError(f"invalid car_id {car}")
        if car in seen:
            raise ValueError(f"duplicate car_id {car}")
        if kind not in TYPE:
            raise ValueError(f"car {car}: acquisition_type must be one of {sorted(TYPE)}")

        item = parse_int(row.get("item_id"))
        cost = parse_int(row.get("cost"))
        unlock = parse_int(row.get("unlock_node_id"))
        class_id = parse_int(row.get("class_id"))
        flags = parse_int(row.get("flags"))

        if cost < 0:
            raise ValueError(f"car {car}: negative cost")
        if kind == "blueprint" and item <= 0:
            raise ValueError(f"car {car}: blueprint acquisition requires item_id")
        if kind != "blueprint" and item != 0:
            raise ValueError(f"car {car}: item_id must be 0 outside blueprint acquisition")

        out.append((car, TYPE[kind], item, cost, unlock, class_id, flags, 0))
        seen.add(car)

    out.sort(key=lambda x: x[0])

    if len(out) > MAX:
        raise ValueError(f"too many vehicles: {len(out)} > {MAX}")
    return out


def build(entries):
    # Fixed-size file matches the no-CRT in-memory C structure exactly.
    body = bytearray()
    body += HEADER.pack(MAGIC, VERSION, len(entries), 0)

    for row in entries:
        body += ENTRY.pack(*row)

    for _ in range(MAX - len(entries)):
        body += ENTRY.pack(0,0,0,0,0,0,0,0)

    checksum = fnv1a(body)
    body += struct.pack("<I", checksum)
    return bytes(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="JSON or CSV Campaign vehicle catalog")
    ap.add_argument("-o", "--output", type=Path, default=Path("CampaignCatalog.dat"))
    ns = ap.parse_args()

    rows = read_csv(ns.input) if ns.input.suffix.lower() == ".csv" else read_json(ns.input)
    entries = normalize(rows)
    data = build(entries)

    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_bytes(data)

    print(f"CampaignCatalog.dat: {len(entries)} vehicles, {len(data)} bytes")


if __name__ == "__main__":
    main()
