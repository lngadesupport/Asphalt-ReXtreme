#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import struct
from pathlib import Path

MAGIC = 0x53455852  # RXES
VERSION = 1
MAX_EVENTS = 64
MAX_STAGES = 16
HEADER = struct.Struct("<4I")
ENTRY = struct.Struct("<iIiIIIII16i")
EVENT_HEADER = struct.Struct("<4I")
EVENT_ENTRY = struct.Struct("<10i")
EVENT_MAGIC = 0x45435852
EVENT_MAX = 512

SCHEDULES = {
    "permanent": 1,
    "daily": 2,
    "weekly": 3,
    "monthly": 4,
    "unlock": 5,
    "manual": 6,
}
FLAG_MANUAL_ACTIVE = 1


class SpecialEventError(RuntimeError):
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
        raise SpecialEventError(f"{name}: bool is not integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise SpecialEventError(f"{name}: invalid integer") from exc
    if result < -0x80000000 or result > 0x7FFFFFFF:
        raise SpecialEventError(f"{name}: out of i32 range")
    return result


def day_key(value, name: str) -> int:
    if value in (None, "", 0, "0"):
        return 0
    if isinstance(value, int):
        key = value
        text = f"{value:08d}"
    elif isinstance(value, str):
        text = value.replace("-", "")
        if len(text) != 8 or not text.isdigit():
            raise SpecialEventError(f"{name}: expected YYYY-MM-DD or YYYYMMDD")
        key = int(text)
    else:
        raise SpecialEventError(f"{name}: invalid date")
    try:
        dt.date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError as exc:
        raise SpecialEventError(f"{name}: invalid calendar date") from exc
    return key


def load_event_ids(path: Path | None) -> set[int] | None:
    if path is None:
        return None
    raw = path.read_bytes()
    expected = EVENT_HEADER.size + EVENT_ENTRY.size * EVENT_MAX + 4
    if len(raw) != expected:
        raise SpecialEventError(f"CampaignEvents.dat: unexpected size {len(raw)}")
    magic, version, count, _ = EVENT_HEADER.unpack_from(raw, 0)
    if magic != EVENT_MAGIC or version != 1 or count > EVENT_MAX:
        raise SpecialEventError("CampaignEvents.dat: invalid header")
    if struct.unpack_from("<I", raw, len(raw) - 4)[0] != fnv1a(raw[:-4]):
        raise SpecialEventError("CampaignEvents.dat: checksum mismatch")
    ids: set[int] = set()
    off = EVENT_HEADER.size
    for i in range(count):
        row = EVENT_ENTRY.unpack_from(raw, off + i * EVENT_ENTRY.size)
        event_id = row[0]
        if event_id <= 0 or event_id in ids:
            raise SpecialEventError("CampaignEvents.dat: invalid event ids")
        ids.add(event_id)
    return ids


def load_source(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != "rextreme-campaign-special-events":
        raise SpecialEventError("invalid format")
    if data.get("version") != VERSION:
        raise SpecialEventError("unsupported version")
    rows = data.get("special_events")
    if not isinstance(rows, list):
        raise SpecialEventError("special_events must be array")
    if len(rows) > MAX_EVENTS:
        raise SpecialEventError(f"too many Special Events: {len(rows)} > {MAX_EVENTS}")
    return rows


def normalize(rows: list[dict], event_ids: set[int] | None) -> list[tuple]:
    result: list[tuple] = []
    seen: set[int] = set()

    if rows and event_ids is None:
        raise SpecialEventError(
            "non-empty Special Event catalog requires --event-catalog CampaignEvents.dat"
        )

    for raw in rows:
        if not isinstance(raw, dict):
            raise SpecialEventError("Special Event must be object")
        ident = integer(raw.get("id"), "id")
        if ident <= 0:
            raise SpecialEventError("id must be positive")
        if ident in seen:
            raise SpecialEventError(f"duplicate Special Event id {ident}")
        seen.add(ident)

        schedule_name = raw.get("schedule", "permanent")
        if schedule_name not in SCHEDULES:
            raise SpecialEventError(f"{ident}: invalid schedule {schedule_name!r}")
        schedule = SCHEDULES[schedule_name]
        required_node = integer(raw.get("required_node_id", 0), f"{ident}.required_node_id")
        if required_node < 0:
            raise SpecialEventError(f"{ident}: required_node_id must be >= 0")

        start = day_key(raw.get("start_date"), f"{ident}.start_date")
        end = day_key(raw.get("end_date"), f"{ident}.end_date")
        if start and end and start > end:
            raise SpecialEventError(f"{ident}: start_date after end_date")

        active = raw.get("active", False)
        if not isinstance(active, bool):
            raise SpecialEventError(f"{ident}: active must be boolean")
        if schedule_name != "manual" and active:
            raise SpecialEventError(f"{ident}: active is only valid for manual schedule")
        flags = FLAG_MANUAL_ACTIVE if active else 0

        stages = raw.get("stages")
        if not isinstance(stages, list) or not stages:
            raise SpecialEventError(f"{ident}: stages must be non-empty array")
        if len(stages) > MAX_STAGES:
            raise SpecialEventError(f"{ident}: too many stages")
        stage_ids: list[int] = []
        local_seen: set[int] = set()
        for idx, value in enumerate(stages):
            event_id = integer(value, f"{ident}.stages[{idx}]")
            if event_id <= 0:
                raise SpecialEventError(f"{ident}: stage event id must be positive")
            if event_id in local_seen:
                raise SpecialEventError(f"{ident}: duplicate stage event id {event_id}")
            if event_ids is not None and event_id not in event_ids:
                raise SpecialEventError(
                    f"{ident}: stage event {event_id} not found in CampaignEvents.dat"
                )
            local_seen.add(event_id)
            stage_ids.append(event_id)
        stage_ids.extend([0] * (MAX_STAGES - len(stage_ids)))

        result.append((
            ident,
            schedule,
            required_node,
            len(stages),
            start,
            end,
            flags,
            0,
            *stage_ids,
        ))

    result.sort(key=lambda row: row[0])
    return result


def build(source: Path, output: Path, event_catalog: Path | None = None, report: Path | None = None) -> dict:
    rows = load_source(source)
    ids = load_event_ids(event_catalog)
    entries = normalize(rows, ids)

    payload = bytearray(HEADER.pack(MAGIC, VERSION, len(entries), 0))
    for entry in entries:
        payload += ENTRY.pack(*entry)
    payload += ENTRY.pack(*([0] * 24)) * (MAX_EVENTS - len(entries))
    payload += struct.pack("<I", fnv1a(payload))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)

    summary = {
        "format": "rextreme-special-event-runtime-catalog",
        "version": VERSION,
        "count": len(entries),
        "output": str(output),
        "validated_against_event_catalog": event_catalog is not None,
        "event_ids": [row[0] for row in entries],
        "uses_existing_campaign_events_only": True,
        "online_backend_required": False,
    }
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Build offline ReXtreme Special Event catalog")
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--event-catalog", type=Path)
    ap.add_argument("--report", type=Path)
    ns = ap.parse_args()
    try:
        summary = build(ns.source, ns.output, ns.event_catalog, ns.report)
    except (OSError, json.JSONDecodeError, SpecialEventError, struct.error) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
