#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import struct
from pathlib import Path

MAGIC = 0x45435852
VERSION = 1
MAX = 512

HEADER = struct.Struct("<4I")
ENTRY = struct.Struct("<10i")


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
    if isinstance(obj, dict) and "events" in obj:
        return obj["events"]
    if isinstance(obj, list):
        return obj
    raise ValueError("JSON must be an array or contain events[]")


def normalize(rows):
    out = []
    seen = set()

    for row in rows:
        event_id = parse_int(row.get("event_id"))
        if event_id <= 0:
            raise ValueError(f"invalid event_id {event_id}")
        if event_id in seen:
            raise ValueError(f"duplicate event_id {event_id}")

        vals = (
            event_id,
            parse_int(row.get("required_node_id")),
            parse_int(row.get("completion_node_id")),
            parse_int(row.get("participation_credits")),
            parse_int(row.get("position1_credits")),
            parse_int(row.get("position2_credits")),
            parse_int(row.get("position3_credits")),
            parse_int(row.get("premium_reward")),
            parse_int(row.get("max_stars"), 3),
            parse_int(row.get("flags")),
        )

        if any(x < 0 for x in vals[1:8]):
            raise ValueError(f"event {event_id}: negative reward/node value")
        if not 0 <= vals[8] <= 10:
            raise ValueError(f"event {event_id}: max_stars outside 0..10")

        out.append(vals)
        seen.add(event_id)

    out.sort(key=lambda x: x[0])
    if len(out) > MAX:
        raise ValueError(f"too many events: {len(out)} > {MAX}")
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
    ap.add_argument("-o", "--output", type=Path, default=Path("CampaignEvents.dat"))
    ns = ap.parse_args()

    rows = read_rows(ns.input)
    entries = normalize(rows)
    data = build(entries)

    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_bytes(data)
    print(f"CampaignEvents.dat: {len(entries)} events, {len(data)} bytes")


if __name__ == "__main__":
    main()
