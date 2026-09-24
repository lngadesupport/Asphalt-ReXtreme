#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

MAGIC = 0x47435852  # RXCG
VERSION = 1
MAX_CHALLENGES = 128
HEADER = struct.Struct("<4I")
ENTRY = struct.Struct("<14i")
CHECKSUM = struct.Struct("<I")

SCOPES = {"permanent": 1, "daily": 2, "weekly": 3}
MODES = {
    "sum_metric": 1,
    "count_matches": 2,
    "best_max": 3,
    "best_min": 4,
}
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
COMPARE = {None: 0, "none": 0, "le": 1, "ge": 2, "eq": 3}


class ChallengeError(RuntimeError):
    pass


def fnv1a(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def as_nonnegative_int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ChallengeError(f"{name} must be a non-negative integer")
    if value > 0x7FFFFFFF:
        raise ChallengeError(f"{name} exceeds int32")
    return value


def normalize(raw: dict, seen: set[int]) -> tuple:
    if not isinstance(raw, dict):
        raise ChallengeError("challenge must be an object")
    challenge_id = raw.get("id")
    if isinstance(challenge_id, bool) or not isinstance(challenge_id, int) or challenge_id <= 0:
        raise ChallengeError("challenge id must be a positive integer")
    if challenge_id in seen:
        raise ChallengeError(f"duplicate challenge id: {challenge_id}")
    seen.add(challenge_id)

    scope_name = raw.get("scope")
    if scope_name not in SCOPES:
        raise ChallengeError(f"{challenge_id}: invalid scope {scope_name!r}")
    metric_name = raw.get("metric")
    if metric_name not in METRICS:
        raise ChallengeError(f"{challenge_id}: invalid metric {metric_name!r}")
    mode_name = raw.get("mode")
    if mode_name not in MODES:
        raise ChallengeError(f"{challenge_id}: invalid mode {mode_name!r}")

    goal = as_nonnegative_int(raw.get("goal"), f"{challenge_id}.goal")
    event_filter = as_nonnegative_int(raw.get("event_filter_id", 0), f"{challenge_id}.event_filter_id")

    qualifier = raw.get("qualifier")
    qualifier_compare = 0
    qualifier_threshold = 0
    if qualifier is not None:
        if not isinstance(qualifier, dict):
            raise ChallengeError(f"{challenge_id}.qualifier must be object")
        compare_name = qualifier.get("compare", "none")
        if compare_name not in COMPARE:
            raise ChallengeError(f"{challenge_id}: invalid qualifier compare")
        qualifier_compare = COMPARE[compare_name]
        qualifier_threshold = as_nonnegative_int(
            qualifier.get("threshold", 0),
            f"{challenge_id}.qualifier.threshold",
        )

    reward = raw.get("reward", {})
    if not isinstance(reward, dict):
        raise ChallengeError(f"{challenge_id}.reward must be object")
    credits = as_nonnegative_int(reward.get("credits", 0), f"{challenge_id}.reward.credits")
    premium = as_nonnegative_int(reward.get("premium", 0), f"{challenge_id}.reward.premium")
    item_id = as_nonnegative_int(reward.get("item_id", 0), f"{challenge_id}.reward.item_id")
    item_amount = as_nonnegative_int(reward.get("item_amount", 0), f"{challenge_id}.reward.item_amount")
    if (item_id == 0) != (item_amount == 0):
        raise ChallengeError(f"{challenge_id}: item_id and item_amount must both be zero or both positive")

    flags = as_nonnegative_int(raw.get("flags", 0), f"{challenge_id}.flags")

    return (
        challenge_id,
        SCOPES[scope_name],
        METRICS[metric_name],
        MODES[mode_name],
        goal,
        event_filter,
        qualifier_compare,
        qualifier_threshold,
        credits,
        premium,
        item_id,
        item_amount,
        flags,
        0,
    )


def build(source: Path, output: Path, report: Path | None = None) -> dict:
    data = json.loads(source.read_text(encoding="utf-8"))
    if data.get("format") != "rextreme-campaign-challenges":
        raise ChallengeError("invalid format")
    if data.get("version") != VERSION:
        raise ChallengeError("unsupported version")
    challenges = data.get("challenges")
    if not isinstance(challenges, list):
        raise ChallengeError("challenges must be an array")
    if len(challenges) > MAX_CHALLENGES:
        raise ChallengeError(f"too many challenges: {len(challenges)}")

    seen: set[int] = set()
    rows = [normalize(x, seen) for x in challenges]
    rows.sort(key=lambda x: x[0])

    body = bytearray()
    body += HEADER.pack(MAGIC, VERSION, len(rows), 0)
    for row in rows:
        body += ENTRY.pack(*row)
    body += b"\0" * ((MAX_CHALLENGES - len(rows)) * ENTRY.size)
    body += CHECKSUM.pack(fnv1a(body))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(body)

    summary = {
        "format": "rextreme-campaign-challenge-catalog",
        "version": VERSION,
        "count": len(rows),
        "entry_size": ENTRY.size,
        "file_size": len(body),
        "ids": [x[0] for x in rows],
        "output": str(output),
    }
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Build ReXtreme offline Campaign challenge catalog")
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--report", type=Path)
    ns = ap.parse_args()
    try:
        result = build(ns.source, ns.output, ns.report)
    except (OSError, json.JSONDecodeError, ChallengeError, struct.error) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
