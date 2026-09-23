#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from build_campaign_event_catalog_from_package import discover_career, intv
from build_campaign_objective_catalog import build, normalize

STAR_NAMES = ("first", "second", "third")
INDEX = {"first": 1, "second": 2, "third": 3}

# Canonical Campaign metric + comparison for original objective names.
# Aliases are normalized before lookup.
ALIASES = {
    "placement": ("placement", "<="),
    "position": ("placement", "<="),
    "position_in_race": ("placement", "<="),
    "finish_position": ("placement", "<="),

    "finish_time": ("finish_time_ms", "<="),
    "finish_time_ms": ("finish_time_ms", "<="),
    "race_time": ("finish_time_ms", "<="),
    "race_time_ms": ("finish_time_ms", "<="),
    "time": ("finish_time_ms", "<="),

    "drift": ("drift_meters", ">="),
    "drift_distance": ("drift_meters", ">="),
    "drift_meters": ("drift_meters", ">="),

    "air_time": ("air_time_ms", ">="),
    "air_time_ms": ("air_time_ms", ">="),
    "airtime": ("air_time_ms", ">="),

    "nitro_time": ("nitro_time_ms", ">="),
    "nitro_time_ms": ("nitro_time_ms", ">="),

    "wrecked_cars": ("wrecked_cars", ">="),
    "cars_wrecked": ("wrecked_cars", ">="),
    "wreck_cars": ("wrecked_cars", ">="),

    "wrecked_environment": ("wrecked_environment", ">="),
    "environment_wrecked": ("wrecked_environment", ">="),

    "wrecks_made": ("wrecks_made", ">="),
    "wrecks": ("wrecks_made", ">="),

    "flat_spins": ("flat_spins", ">="),
    "flat_spin": ("flat_spins", ">="),
    "flat_jumps": ("flat_spins", ">="),

    "barrel_rolls": ("barrel_rolls", ">="),
    "barrel_roll": ("barrel_rolls", ">="),

    "obstacles_broken": ("obstacles_broken", ">="),
    "obstacles": ("obstacles_broken", ">="),

    "nitro_all_in": ("nitro_all_in", ">="),
    "all_in_nitro": ("nitro_all_in", ">="),

    "nitro_chain": ("nitro_chain", ">="),
    "nitro_chains": ("nitro_chain", ">="),

    "nitro_normal": ("nitro_normal", ">="),
    "normal_nitro": ("nitro_normal", ">="),
}

TYPE_KEYS = (
    "type", "metric", "objective_type", "condition_type", "goal_type",
    "star_type", "requirement_type", "objective"
)
VALUE_KEYS = (
    "value", "amount", "threshold", "target", "objective_value",
    "condition_value", "goal_value", "requirement", "required"
)


def norm_token(value: object) -> str:
    s = str(value).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def int_like(value: object) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    s = str(value).strip()
    m = re.fullmatch(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    return int(round(float(s)))


def convert_threshold(metric: str, raw: int, source_type: str) -> int:
    if raw < 0:
        raise ValueError("negative objective threshold")

    t = source_type.lower()

    # Career configs sometimes store seconds/meters as decimal-friendly values.
    # We convert only when the key explicitly denotes seconds.
    if metric in ("finish_time_ms", "air_time_ms", "nitro_time_ms"):
        if re.search(r"(?:^|_)seconds?(?:_|$)", t) or t.endswith("_sec") or t.endswith("_secs"):
            return raw * 1000
    return raw


def objective_from_pair(event_id: int, index: int, type_value: object, threshold_value: object, source: str):
    token = norm_token(type_value)
    if token not in ALIASES:
        return None, {
            "event_id": event_id,
            "objective_index": index,
            "source": source,
            "type": type_value,
            "threshold": threshold_value,
            "reason": "unknown objective type",
        }

    threshold = int_like(threshold_value)
    if threshold is None:
        return None, {
            "event_id": event_id,
            "objective_index": index,
            "source": source,
            "type": type_value,
            "threshold": threshold_value,
            "reason": "objective threshold is not numeric",
        }

    metric, compare = ALIASES[token]
    threshold = convert_threshold(metric, threshold, token)
    return {
        "event_id": event_id,
        "objective_index": index,
        "metric": metric,
        "compare": compare,
        "threshold": threshold,
        "stars": 1,
        "flags": 0,
    }, None


def dict_type_value(obj: dict):
    type_key = next((k for k in TYPE_KEYS if k in obj and obj[k] not in (None, "")), None)
    value_key = next((k for k in VALUE_KEYS if k in obj and obj[k] not in (None, "")), None)
    if type_key and value_key:
        return obj[type_key], obj[value_key], f"{type_key}+{value_key}"
    return None


def inspect_star_object(event: dict, star: str):
    # Common flat pairs.
    type_candidates = (
        f"{star}_star_type",
        f"{star}_star_objective_type",
        f"{star}_star_condition_type",
        f"{star}_objective_type",
        f"{star}_condition_type",
        f"star_{INDEX[star]}_type",
        f"star{INDEX[star]}_type",
    )
    value_candidates = (
        f"{star}_star_value",
        f"{star}_star_objective_value",
        f"{star}_star_condition_value",
        f"{star}_objective_value",
        f"{star}_condition_value",
        f"star_{INDEX[star]}_value",
        f"star{INDEX[star]}_value",
        f"{star}_star_amount",
        f"star_{INDEX[star]}_amount",
    )

    tk = next((k for k in type_candidates if k in event and event[k] not in (None, "")), None)
    vk = next((k for k in value_candidates if k in event and event[k] not in (None, "")), None)
    if tk or vk:
        return (event.get(tk) if tk else None, event.get(vk) if vk else None, f"{tk}+{vk}")

    # Common nested star objects.
    nested_keys = (
        f"{star}_star",
        f"star_{INDEX[star]}",
        f"star{INDEX[star]}",
        f"{star}_objective",
    )
    for key in nested_keys:
        value = event.get(key)
        if isinstance(value, dict):
            pair = dict_type_value(value)
            if pair:
                return pair[0], pair[1], f"{key}.{pair[2]}"
    return None


def inspect_objective_list(event: dict):
    for key in ("objectives", "star_objectives", "stars", "goals", "conditions"):
        value = event.get(key)
        if not isinstance(value, list):
            continue
        rows = []
        for i, item in enumerate(value[:3], 1):
            if not isinstance(item, dict):
                rows.append((i, None, None, f"{key}[{i-1}]"))
                continue
            pair = dict_type_value(item)
            if pair:
                rows.append((i, pair[0], pair[1], f"{key}[{i-1}].{pair[2]}"))
            else:
                rows.append((i, None, None, f"{key}[{i-1}]"))
        if rows:
            return rows
    return None


def candidate_fields(event: dict) -> dict:
    out = {}
    for k, v in event.items():
        lk = k.lower()
        if any(word in lk for word in (
            "star", "objective", "condition", "goal", "drift", "wreck",
            "barrel", "flat", "nitro", "air", "time", "position", "obstacle"
        )):
            if isinstance(v, (str, int, float, bool)) or v is None:
                out[k] = v
            elif isinstance(v, list):
                out[k] = v[:3]
            elif isinstance(v, dict):
                out[k] = v
    return out


def convert(career: dict):
    rows = []
    unresolved = []
    source_fields = {}

    for event in career.get("events", []):
        if not isinstance(event, dict):
            continue

        event_id = intv(event, "eventid", intv(event, "id"))
        if event_id <= 0:
            continue

        list_rows = inspect_objective_list(event)
        if list_rows:
            for idx, t, v, source in list_rows:
                row, error = objective_from_pair(event_id, idx, t, v, source)
                if row:
                    rows.append(row)
                else:
                    error["candidate_fields"] = candidate_fields(event)
                    unresolved.append(error)
            continue

        found_any = False
        for star in STAR_NAMES:
            pair = inspect_star_object(event, star)
            if not pair:
                continue
            found_any = True
            idx = INDEX[star]
            row, error = objective_from_pair(event_id, idx, pair[0], pair[1], pair[2])
            if row:
                rows.append(row)
            else:
                error["candidate_fields"] = candidate_fields(event)
                unresolved.append(error)

        if not found_any:
            source_fields[str(event_id)] = candidate_fields(event)
            unresolved.append({
                "event_id": event_id,
                "reason": "no recognized objective structure",
                "candidate_fields": source_fields[str(event_id)],
            })

    return rows, unresolved


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Strictly reconstruct CampaignObjectives.dat from real career data"
    )
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument(
        "--allow-empty",
        action="store_true",
        help="diagnostic only; write an empty catalog instead of failing"
    )
    ns = ap.parse_args()

    package = ns.package.resolve()
    if not package.is_dir():
        raise SystemExit(f"package directory not found: {package}")

    source, career = discover_career(package)
    rows, unresolved = convert(career)

    report = {
        "career_source": str(source),
        "recognized_objectives": len(rows),
        "unresolved_count": len(unresolved),
        "unresolved": unresolved,
        "objectives": rows,
    }
    ns.report.parent.mkdir(parents=True, exist_ok=True)
    ns.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if unresolved and not ns.allow_empty:
        print(json.dumps({
            "status": "needs-mapping",
            "recognized_objectives": len(rows),
            "unresolved_count": len(unresolved),
            "report": str(ns.report),
        }, indent=2, ensure_ascii=False))
        raise SystemExit(3)

    entries = normalize(rows)
    payload = build(entries)
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_bytes(payload)

    print(json.dumps({
        "status": "ok",
        "career_source": str(source),
        "objective_count": len(rows),
        "output": str(ns.output),
        "report": str(ns.report),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
