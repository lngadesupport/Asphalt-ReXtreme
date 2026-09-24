#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

MAGIC = 0x48435852  # RXCH
VERSION = 1
MAX_CHAMPIONSHIPS = 64
MAX_ROUNDS = 16
MAX_POSITIONS = 7
HEADER = struct.Struct("<4I")
ENTRY = struct.Struct("<iiII16i7i")
EVENT_HEADER = struct.Struct("<4I")
EVENT_ENTRY = struct.Struct("<10i")
EVENT_MAGIC = 0x45435852
EVENT_MAX = 512

class ChampionshipError(RuntimeError):
    pass

def fnv1a(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h

def integer(value, name: str, default=0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ChampionshipError(f"{name}: bool is not integer")
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise ChampionshipError(f"{name}: invalid integer") from exc
    if out < -0x80000000 or out > 0x7FFFFFFF:
        raise ChampionshipError(f"{name}: out of i32 range")
    return out

def load_event_ids(path: Path | None) -> set[int] | None:
    if path is None:
        return None
    raw = path.read_bytes()
    expected = EVENT_HEADER.size + EVENT_ENTRY.size * EVENT_MAX + 4
    if len(raw) != expected:
        raise ChampionshipError(f"CampaignEvents.dat: unexpected size {len(raw)}")
    magic, version, count, _ = EVENT_HEADER.unpack_from(raw, 0)
    if magic != EVENT_MAGIC or version != 1 or count > EVENT_MAX:
        raise ChampionshipError("CampaignEvents.dat: invalid header")
    if struct.unpack_from("<I", raw, len(raw)-4)[0] != fnv1a(raw[:-4]):
        raise ChampionshipError("CampaignEvents.dat: checksum mismatch")
    ids: set[int] = set()
    off = EVENT_HEADER.size
    for i in range(count):
        row = EVENT_ENTRY.unpack_from(raw, off + i * EVENT_ENTRY.size)
        event_id = row[0]
        if event_id <= 0 or event_id in ids:
            raise ChampionshipError("CampaignEvents.dat: invalid event ids")
        ids.add(event_id)
    return ids

def load_source(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != "rextreme-campaign-championships":
        raise ChampionshipError("invalid format")
    if data.get("version") != VERSION:
        raise ChampionshipError("unsupported version")
    rows = data.get("championships")
    if not isinstance(rows, list) or len(rows) > MAX_CHAMPIONSHIPS:
        raise ChampionshipError("championships must be array <=64")
    return rows

def normalize(rows: list[dict], event_ids: set[int] | None) -> list[tuple]:
    if rows and event_ids is None:
        raise ChampionshipError("non-empty Championship catalog requires --event-catalog")
    result = []
    seen: set[int] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            raise ChampionshipError("championship must be object")
        ident = integer(raw.get("id"), "id")
        if ident <= 0:
            raise ChampionshipError("id must be positive")
        if ident in seen:
            raise ChampionshipError(f"duplicate championship id {ident}")
        seen.add(ident)

        required = integer(raw.get("required_node_id", 0), f"{ident}.required_node_id")
        if required < 0:
            raise ChampionshipError(f"{ident}: required_node_id must be >=0")
        flags = integer(raw.get("flags", 0), f"{ident}.flags")
        if flags < 0:
            raise ChampionshipError(f"{ident}: flags must be >=0")

        rounds = raw.get("rounds")
        if not isinstance(rounds, list) or not rounds or len(rounds) > MAX_ROUNDS:
            raise ChampionshipError(f"{ident}: rounds must contain 1..{MAX_ROUNDS} event ids")
        round_ids: list[int] = []
        local: set[int] = set()
        for idx, value in enumerate(rounds):
            event_id = integer(value, f"{ident}.rounds[{idx}]")
            if event_id <= 0:
                raise ChampionshipError(f"{ident}: round event id must be positive")
            if event_id in local:
                raise ChampionshipError(f"{ident}: duplicate round event {event_id}")
            if event_ids is not None and event_id not in event_ids:
                raise ChampionshipError(f"{ident}: event {event_id} missing from CampaignEvents.dat")
            local.add(event_id)
            round_ids.append(event_id)
        round_ids += [0] * (MAX_ROUNDS - len(round_ids))

        points = raw.get("points")
        if not isinstance(points, list) or len(points) != MAX_POSITIONS:
            raise ChampionshipError(f"{ident}: points must contain exactly 7 values")
        point_values = [integer(v, f"{ident}.points[{i}]") for i, v in enumerate(points)]
        if point_values[0] <= 0 or any(v < 0 for v in point_values):
            raise ChampionshipError(f"{ident}: points must be non-negative and P1 > 0")
        if any(point_values[i] > point_values[i-1] for i in range(1, MAX_POSITIONS)):
            raise ChampionshipError(f"{ident}: points must be non-increasing by placement")

        result.append((ident, required, len(rounds), flags, *round_ids, *point_values))

    result.sort(key=lambda row: row[0])
    return result

def build(source: Path, output: Path, event_catalog: Path | None = None, report: Path | None = None) -> dict:
    rows = normalize(load_source(source), load_event_ids(event_catalog))
    payload = bytearray(HEADER.pack(MAGIC, VERSION, len(rows), 0))
    for row in rows:
        payload += ENTRY.pack(*row)
    payload += ENTRY.pack(*([0] * 27)) * (MAX_CHAMPIONSHIPS - len(rows))
    payload += struct.pack("<I", fnv1a(payload))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    summary = {
        "format": "rextreme-campaign-championship-runtime-catalog",
        "version": VERSION,
        "count": len(rows),
        "entry_size": ENTRY.size,
        "output": str(output),
        "validated_against_event_catalog": event_catalog is not None,
        "uses_existing_campaign_events_only": True,
        "online_backend_required": False,
        "ids": [row[0] for row in rows],
    }
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary

def main() -> int:
    ap = argparse.ArgumentParser(description="Build offline ReXtreme Championship catalog")
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--event-catalog", type=Path)
    ap.add_argument("--report", type=Path)
    ns = ap.parse_args()
    try:
        result = build(ns.source, ns.output, ns.event_catalog, ns.report)
    except (OSError, json.JSONDecodeError, ChampionshipError, struct.error) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
