#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

MAGIC = 0x4F435852
VERSION = 1
MAX = 1536

HEADER = struct.Struct("<4I")
ENTRY = struct.Struct("<8i")
CHECKSUM = struct.Struct("<I")

METRICS = {
    "placement": 1,
    "finish_time_ms": 2,
    "drift_meters": 3,
    "air_time_ms": 4,
    "nitro_time_ms": 5,
    "wrecked_cars": 6,
    "wrecked_environment": 7,
    "wrecks_made": 8,
    "flat_spins": 9,
    "barrel_rolls": 10,
    "obstacles_broken": 11,
    "nitro_all_in": 12,
    "nitro_chain": 13,
    "nitro_normal": 14,
}

COMPARE = {
    "le": 1,
    "<=": 1,
    "ge": 2,
    ">=": 2,
    "eq": 3,
    "==": 3,
}


def fnv1a(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def read_rows(path: Path) -> list[dict]:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if int(obj.get("schema", 0)) != 1:
        raise ValueError("expected schema=1")
    rows = obj.get("objectives")
    if not isinstance(rows, list):
        raise ValueError("expected objectives[]")
    return rows


def normalize(rows: list[dict]) -> list[tuple[int, ...]]:
    out = []
    seen = set()

    for row in rows:
        event_id = int(row["event_id"])
        objective_index = int(row["objective_index"])
        metric_name = str(row["metric"]).strip().lower()
        compare_name = str(row["compare"]).strip().lower()
        threshold = int(row["threshold"])
        stars = int(row.get("stars", 1))
        flags = int(row.get("flags", 0))

        if event_id <= 0:
            raise ValueError("event_id must be positive")
        if objective_index not in (1, 2, 3):
            raise ValueError("objective_index must be 1..3")
        if metric_name not in METRICS:
            raise ValueError(f"unknown metric {metric_name!r}")
        if compare_name not in COMPARE:
            raise ValueError(f"unknown comparison {compare_name!r}")
        if threshold < 0:
            raise ValueError("threshold must be non-negative")
        if not 0 <= stars <= 3:
            raise ValueError("stars must be 0..3")

        key = (event_id, objective_index)
        if key in seen:
            raise ValueError(f"duplicate objective key {key}")
        seen.add(key)

        out.append((
            event_id,
            objective_index,
            METRICS[metric_name],
            COMPARE[compare_name],
            threshold,
            stars,
            flags,
            0,
        ))

    out.sort(key=lambda x: x[:2])
    if len(out) > MAX:
        raise ValueError(f"too many objectives: {len(out)} > {MAX}")
    return out


def build(entries: list[tuple[int, ...]]) -> bytes:
    body = bytearray(HEADER.pack(MAGIC, VERSION, len(entries), 0))
    for row in entries:
        body += ENTRY.pack(*row)
    body += ENTRY.pack(*([0] * 8)) * (MAX - len(entries))
    body += CHECKSUM.pack(fnv1a(body))
    return bytes(body)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=Path("CampaignObjectives.dat"))
    ns = ap.parse_args()

    entries = normalize(read_rows(ns.input))
    data = build(entries)
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_bytes(data)
    print(f"CampaignObjectives.dat: {len(entries)} objectives, {len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
