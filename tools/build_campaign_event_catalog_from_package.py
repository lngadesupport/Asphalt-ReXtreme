#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_campaign_event_catalog import build, normalize


def discover_career(root: Path) -> tuple[Path, dict]:
    hits: list[tuple[Path, dict]] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size <= 0 or path.stat().st_size > 64 * 1024 * 1024:
                continue
        except OSError:
            continue

        try:
            raw = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue

        if '"events"' not in raw or '"seasons"' not in raw:
            continue
        if '"money_for_playing"' not in raw and '"position_1"' not in raw:
            continue

        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if not isinstance(obj, dict):
            continue
        events = obj.get("events")
        seasons = obj.get("seasons")
        if not isinstance(events, list) or not isinstance(seasons, list) or not events:
            continue

        if not any(isinstance(e, dict) and ("eventid" in e or "id" in e) for e in events):
            continue

        hits.append((path, obj))

    if len(hits) != 1:
        raise RuntimeError(
            f"expected exactly one career JSON, found {len(hits)}: "
            + ", ".join(str(p) for p, _ in hits)
        )
    return hits[0]


def intv(obj: dict, key: str, default: int = 0) -> int:
    v = obj.get(key, default)
    if v in (None, ""):
        return default
    return int(v)


def convert(career: dict) -> list[dict]:
    rows: list[dict] = []

    for event in career["events"]:
        if not isinstance(event, dict):
            continue

        event_id = intv(event, "eventid", intv(event, "id"))
        if event_id <= 0:
            continue

        unlock = intv(event, "unlockeventid")
        participation = max(0, intv(event, "money_for_playing"))
        p1 = max(0, intv(event, "position_1"))
        p2 = max(0, intv(event, "position_2"))
        p3 = max(0, intv(event, "position_3"))

        # Campaign progression uses event_id itself as the local completion node.
        # The original unlockeventid becomes the required local node.
        rows.append({
            "event_id": event_id,
            "required_node_id": max(0, unlock),
            "completion_node_id": event_id,
            "participation_credits": participation,
            "position1_credits": p1,
            "position2_credits": p2,
            "position3_credits": p3,
            "premium_reward": 0,
            "max_stars": 3,
            "flags": 0,
        })

    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Build CampaignEvents.dat from the extracted package career data")
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, default=None)
    ns = ap.parse_args()

    package = ns.package.resolve()
    if not package.is_dir():
        raise SystemExit(f"package directory not found: {package}")

    source, career = discover_career(package)
    rows = convert(career)
    entries = normalize(rows)
    payload = build(entries)

    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_bytes(payload)

    report_path = ns.report or ns.output.with_suffix(".json")
    report_path.write_text(
        json.dumps({
            "career_source": str(source),
            "event_count": len(rows),
            "output": str(ns.output),
            "events": rows,
            "note": (
                "Credits and unlock dependencies are imported from career data. "
                "premium_reward is intentionally zero until Campaign reward objectives "
                "are bound explicitly, avoiding accidental repeatable premium payouts."
            ),
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps({
        "career_source": str(source),
        "event_count": len(rows),
        "output": str(ns.output),
        "report": str(report_path),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
