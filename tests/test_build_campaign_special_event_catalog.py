from __future__ import annotations

import importlib.util
import json
import struct
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "tools" / "build_campaign_special_event_catalog.py"
spec = importlib.util.spec_from_file_location("build_campaign_special_event_catalog", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def write_source(path: Path, rows: list[dict]):
    path.write_text(json.dumps({
        "format": "rextreme-campaign-special-events",
        "version": 1,
        "special_events": rows,
    }), encoding="utf-8")


def write_events(path: Path, ids: list[int]):
    body = bytearray(mod.EVENT_HEADER.pack(mod.EVENT_MAGIC, 1, len(ids), 0))
    for event_id in ids:
        body += mod.EVENT_ENTRY.pack(
            event_id, 0, event_id, 100, 200, 100, 50, 0, 3, 0
        )
    body += mod.EVENT_ENTRY.pack(*([0] * 10)) * (mod.EVENT_MAX - len(ids))
    body += struct.pack("<I", mod.fnv1a(body))
    path.write_bytes(body)


def test_empty_catalog_is_safe_without_event_catalog(tmp_path: Path):
    src = tmp_path / "special.json"
    out = tmp_path / "CampaignSpecialEvents.dat"
    write_source(src, [])
    summary = mod.build(src, out)
    assert summary["count"] == 0
    assert summary["uses_existing_campaign_events_only"] is True
    assert summary["online_backend_required"] is False
    assert len(out.read_bytes()) == mod.HEADER.size + mod.ENTRY.size * mod.MAX_EVENTS + 4


def test_nonempty_requires_campaign_event_catalog(tmp_path: Path):
    src = tmp_path / "special.json"
    out = tmp_path / "out.dat"
    write_source(src, [{
        "id": 5001,
        "schedule": "permanent",
        "stages": [1001],
    }])
    try:
        mod.build(src, out)
    except mod.SpecialEventError as exc:
        assert "--event-catalog" in str(exc)
    else:
        raise AssertionError("non-empty Special Event catalog accepted without event catalog")


def test_stage_ids_are_cross_validated(tmp_path: Path):
    src = tmp_path / "special.json"
    events = tmp_path / "CampaignEvents.dat"
    out = tmp_path / "out.dat"
    write_events(events, [1001, 1002, 1003])
    write_source(src, [{
        "id": 5001,
        "schedule": "permanent",
        "stages": [1001, 9999],
    }])
    try:
        mod.build(src, out, events)
    except mod.SpecialEventError as exc:
        assert "9999" in str(exc)
    else:
        raise AssertionError("unknown stage event was accepted")


def test_valid_special_event_builds(tmp_path: Path):
    src = tmp_path / "special.json"
    events = tmp_path / "CampaignEvents.dat"
    out = tmp_path / "out.dat"
    write_events(events, [1001, 1002, 1003])
    write_source(src, [{
        "id": 5001,
        "schedule": "weekly",
        "required_node_id": 5,
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "stages": [1001, 1002, 1003],
    }])
    summary = mod.build(src, out, events)
    assert summary["count"] == 1
    assert summary["validated_against_event_catalog"] is True
    assert summary["event_ids"] == [5001]


def test_manual_active_only_allowed_for_manual_schedule(tmp_path: Path):
    src = tmp_path / "special.json"
    events = tmp_path / "CampaignEvents.dat"
    out = tmp_path / "out.dat"
    write_events(events, [1001])
    write_source(src, [{
        "id": 5001,
        "schedule": "permanent",
        "active": True,
        "stages": [1001],
    }])
    try:
        mod.build(src, out, events)
    except mod.SpecialEventError as exc:
        assert "manual" in str(exc)
    else:
        raise AssertionError("active flag accepted outside manual schedule")


def test_invalid_calendar_date_is_rejected(tmp_path: Path):
    src = tmp_path / "special.json"
    events = tmp_path / "CampaignEvents.dat"
    out = tmp_path / "out.dat"
    write_events(events, [1001])
    write_source(src, [{
        "id": 5001,
        "schedule": "permanent",
        "start_date": "2026-02-30",
        "stages": [1001],
    }])
    try:
        mod.build(src, out, events)
    except mod.SpecialEventError as exc:
        assert "invalid calendar date" in str(exc)
    else:
        raise AssertionError("invalid calendar date accepted")
