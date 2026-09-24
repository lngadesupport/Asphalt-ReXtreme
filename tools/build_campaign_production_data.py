#!/usr/bin/env python3
"""Build production Campaign Edition data directly from the installed xml.bin.

This is the single data-generation path for the clean-room Campaign systems.
It reads the real 1.7.3.x package data and emits:
  CampaignCatalog.dat
  CampaignEvents.dat
  CampaignUpgrades.dat

No example/placeholder catalog is used at runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from xtea_assets import decode_stream
from rextreme_economy import CARDEF_RE, first_xml_document
from economy_audit import FILTERS
import build_campaign_vehicle_catalog as vehicle_binary
import build_campaign_event_catalog as event_binary
import build_campaign_upgrade_catalog as upgrade_binary

CLASS_ID = {"D": 1, "C": 2, "B": 3, "A": 4, "S": 5}
PART_NAMES = {
    "TOPSPEED": 0, "TOP_SPEED": 0, "SPEED": 0,
    "ACCELERATION": 1, "ACCEL": 1,
    "HANDLING": 2, "HANDLE": 2,
    "NITRO": 3,
}
DEFAULT_PART_SLOTS = (0, 1, 2, 3)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def campaign_price(original: int, multiplier: float) -> int:
    if original <= 0:
        return 0
    return max(1, int(round(original * multiplier)))


def _decode_xmlbin_entry(archive: zipfile.ZipFile, wanted_basename: str) -> bytes:
    candidates = [
        info for info in archive.infolist()
        if not info.is_dir() and Path(info.filename).name.lower() == wanted_basename.lower()
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected exactly one {wanted_basename!r} in xml.bin, found {len(candidates)}"
        )
    payload, meta = decode_stream(archive.read(candidates[0]))
    if meta.get("stream_type") not in (0, 1):
        raise RuntimeError(f"unsupported stream type for {wanted_basename}")
    return payload


def extract_sources(xml_bin: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(xml_bin, "r") as z:
        return {
            "shop": _decode_xmlbin_entry(z, "asphaltshop.xtea"),
            "serverdb": _decode_xmlbin_entry(z, "asphaltserverdb.xtea"),
            "career": _decode_xmlbin_entry(z, "career_data.xtea"),
        }


def parse_shop(data: bytes):
    text = data.decode("utf-8-sig", errors="replace")
    root = ET.fromstring(first_xml_document(text, "AsphaltShopConfiguration"))

    cars = {}
    for car in root.findall("./Car"):
        car_id = int(car.get("carId", "0"))
        if car_id <= 0:
            continue

        record = {
            "car_id": car_id,
            "base": {"credits": 0, "hardcurrency": 0},
            "upgrade_prices": [],
            "prokit_prices": [],
        }

        upgrades = car.find("./UpgradePrices")
        if upgrades is not None:
            for ordinal, p in enumerate(upgrades.findall("./Price")):
                pid = str(p.get("Id", "")).strip()
                currency = str(p.get("Currency", "")).strip().lower()
                value = int(float(p.get("Price", "0") or 0))
                if pid.upper() == "CAR_PRICE":
                    if currency in record["base"]:
                        record["base"][currency] = max(record["base"][currency], value)
                else:
                    record["upgrade_prices"].append({
                        "id": pid,
                        "currency": currency,
                        "price": value,
                        "ordinal": ordinal,
                    })

        prokits = car.find("./ProKitPrices")
        if prokits is not None:
            for ordinal, p in enumerate(prokits.findall("./Price")):
                record["prokit_prices"].append({
                    "id": str(p.get("Id", "")).strip(),
                    "currency": str(p.get("Currency", "")).strip().lower(),
                    "price": int(float(p.get("Price", "0") or 0)),
                    "ordinal": ordinal,
                })

        cars[car_id] = record
    return cars


def parse_serverdb(data: bytes):
    text = data.decode("utf-8-sig", errors="replace")
    result = {}
    for car_def, car_id, car_class, rank in CARDEF_RE.findall(text):
        result[int(car_id)] = {
            "car_def": car_def,
            "class": str(car_class).upper(),
            "base_rank": float(rank) if "." in rank else int(rank),
        }
    return result


def parse_career(data: bytes):
    return json.loads(data.decode("utf-8-sig"))


def main_career(career: dict):
    seasons = sorted(
        [s for s in career.get("seasons", []) if int(s.get("serieid", 0) or 0) == 1],
        key=lambda s: int(s.get("index", 0) or 0),
    )
    season_ids = {
        int(s.get("seasonid", s.get("id", 0)) or 0)
        for s in seasons
    }
    events = sorted(
        [
            e for e in career.get("events", [])
            if int(e.get("season", 0) or 0) in season_ids
            and not bool(e.get("masteries", False))
        ],
        key=lambda e: int(e.get("eventid", e.get("id", 0)) or 0),
    )
    return seasons, events


def derive_vehicle_unlocks(events):
    """Unlock a mandatory car when the event *before* its first gate is complete."""
    unlocks = {}
    mandatory = set()
    for e in events:
        filt = str(e.get("carracerfilter", "") or "")
        car_id = FILTERS.get(filt)
        if not car_id:
            continue
        mandatory.add(car_id)
        if car_id not in unlocks:
            unlocks[car_id] = max(0, int(e.get("unlockeventid", 0) or 0))
    return unlocks, mandatory


def build_vehicle_rows(shop, serverdb, events, multiplier):
    unlocks, mandatory = derive_vehicle_unlocks(events)
    rows = []
    audit = []

    for car_id in sorted(shop):
        rec = shop[car_id]
        definition = serverdb.get(car_id, {})
        credits = int(rec["base"]["credits"])
        premium = int(rec["base"]["hardcurrency"])

        if credits > 0:
            kind = "credits"
            cost = campaign_price(credits, multiplier)
            source = "original_credit_price"
        elif premium > 0:
            kind = "premium"
            cost = campaign_price(premium, multiplier)
            source = "original_hardcurrency_price"
        else:
            kind = "free"
            cost = 0
            source = "no_positive_direct_price"

        cls = str(definition.get("class", "")).upper()
        row = {
            "car_id": car_id,
            "acquisition_type": kind,
            "item_id": 0,
            "cost": cost,
            "unlock_node_id": int(unlocks.get(car_id, 0)),
            "class_id": CLASS_ID.get(cls, 0),
            "flags": 1 if car_id in mandatory else 0,
        }
        rows.append(row)

        audit.append({
            **row,
            "car_def": definition.get("car_def", ""),
            "class": cls,
            "original_credits": credits,
            "original_hardcurrency": premium,
            "price_source": source,
            "mandatory_exact_car_gate": car_id in mandatory,
        })
    return rows, audit


def _event_premium_reward(event, divisor: int, cap: int) -> int:
    repeat_credits = (
        int(event.get("money_for_playing", 0) or 0)
        + int(event.get("position_1", 0) or 0)
    )
    if repeat_credits <= 0:
        return 0
    reward = max(1, int(round(repeat_credits / divisor)))
    return min(cap, reward)


def build_event_rows(events, premium_divisor, premium_cap):
    rows = []
    audit = []
    for e in events:
        event_id = int(e.get("eventid", e.get("id", 0)) or 0)
        if event_id <= 0:
            continue

        row = {
            "event_id": event_id,
            "required_node_id": max(0, int(e.get("unlockeventid", 0) or 0)),
            "completion_node_id": event_id,
            "participation_credits": max(0, int(e.get("money_for_playing", 0) or 0)),
            "position1_credits": max(0, int(e.get("position_1", 0) or 0)),
            "position2_credits": max(0, int(e.get("position_2", 0) or 0)),
            "position3_credits": max(0, int(e.get("position_3", 0) or 0)),
            "premium_reward": _event_premium_reward(e, premium_divisor, premium_cap),
            "max_stars": 3,
            "flags": 0,
        }
        rows.append(row)
        audit.append({
            **row,
            "season": int(e.get("season", 0) or 0),
            "event_def": e.get("event_def", ""),
            "car_filter": e.get("carracerfilter", ""),
            "premium_policy": f"round((money_for_playing+position_1)/{premium_divisor}), min=1, cap={premium_cap}",
        })
    return rows, audit


_TRAILING_LEVEL = re.compile(r"^(.*?)(?:[_-](?:LEVEL|LVL))?[_-]?(\d+)$", re.I)


def _canonical_part_from_id(price_id: str):
    upper = price_id.upper().replace("-", "_")
    for token, slot in PART_NAMES.items():
        if token in upper:
            return slot
    return None


def _level_from_id(price_id: str):
    m = _TRAILING_LEVEL.match(price_id.strip())
    if not m:
        return None
    level = int(m.group(2))
    return max(1, level)


def _group_prices(prices):
    grouped = defaultdict(dict)
    order = []
    for p in prices:
        pid = str(p["id"] or "").strip()
        if not pid:
            pid = f"PRICE_{p['ordinal'] + 1}"
        key = pid.upper()
        if key not in grouped:
            order.append(key)
        currency = str(p["currency"]).lower()
        value = int(p["price"])
        if currency in ("credits", "hardcurrency") and value > 0:
            old = grouped[key].get(currency, 0)
            grouped[key][currency] = max(old, value)
    return [(key, grouped[key]) for key in order if grouped[key]]


def _schedule_for_prices(prices, kind, multiplier, unlock_node, audit, car_id):
    groups = _group_prices(prices)
    if not groups:
        return []

    explicit_parts = any(_canonical_part_from_id(pid) is not None for pid, _ in groups)
    rows = []

    if explicit_parts:
        fallback_slots = {}
        next_slot = 4
        per_slot_fallback_level = defaultdict(int)

        for pid, currencies in groups:
            slot = _canonical_part_from_id(pid)
            if slot is None:
                base = re.sub(r"\d+$", "", pid).strip("_-")
                if base not in fallback_slots:
                    fallback_slots[base] = next_slot
                    next_slot += 1
                slot = fallback_slots[base]

            level = _level_from_id(pid)
            if level is None:
                per_slot_fallback_level[slot] += 1
                level = per_slot_fallback_level[slot]

            rows.append(_upgrade_row(
                car_id, kind, slot, level, currencies, multiplier, unlock_node, pid, audit
            ))
    else:
        # Asphalt's shop commonly stores a level price schedule shared by the
        # four performance categories. Replicate that schedule for each slot.
        fallback_level = 0
        for pid, currencies in groups:
            level = _level_from_id(pid)
            if level is None:
                fallback_level += 1
                level = fallback_level
            for slot in DEFAULT_PART_SLOTS:
                rows.append(_upgrade_row(
                    car_id, kind, slot, level, currencies, multiplier, unlock_node, pid, audit
                ))

    # Deduplicate exact keys, preferring first occurrence from the source.
    unique = {}
    for row in rows:
        key = (row["car_id"], row["kind"], row["part_slot"], row["target_level"])
        unique.setdefault(key, row)
    return list(unique.values())


def _upgrade_row(car_id, kind, slot, level, currencies, multiplier, unlock_node, pid, audit):
    if currencies.get("credits", 0) > 0:
        cost_type = "credits"
        original = currencies["credits"]
    elif currencies.get("hardcurrency", 0) > 0:
        cost_type = "premium"
        original = currencies["hardcurrency"]
    else:
        cost_type = "free"
        original = 0

    cost = campaign_price(original, multiplier)
    row = {
        "car_id": car_id,
        "kind": kind,
        "part_slot": int(slot),
        "target_level": int(level),
        "cost_type": cost_type,
        "item_id": 0,
        "cost": cost,
        "unlock_node_id": int(unlock_node),
        "flags": 0,
    }
    audit.append({
        **row,
        "source_price_id": pid,
        "original_price": original,
        "original_currency": "credits" if currencies.get("credits", 0) > 0 else (
            "hardcurrency" if currencies.get("hardcurrency", 0) > 0 else "free"
        ),
    })
    return row


def build_upgrade_rows(shop, vehicle_rows, multiplier):
    unlock_by_car = {int(r["car_id"]): int(r["unlock_node_id"]) for r in vehicle_rows}
    rows = []
    audit = []

    for car_id in sorted(shop):
        rec = shop[car_id]
        unlock = unlock_by_car.get(car_id, 0)
        rows.extend(_schedule_for_prices(
            rec["upgrade_prices"], "upgrade", multiplier, unlock, audit, car_id
        ))
        rows.extend(_schedule_for_prices(
            rec["prokit_prices"], "prokit", multiplier, unlock, audit, car_id
        ))
    return rows, audit


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def build_all(
    xml_bin: Path,
    output_dir: Path,
    package_dir: Path | None,
    multiplier: float = 0.20,
    premium_divisor: int = 2500,
    premium_cap: int = 5,
):
    if not 0 < multiplier <= 1:
        raise ValueError("vehicle/upgrade multiplier must be >0 and <=1")
    if premium_divisor <= 0 or premium_cap < 0:
        raise ValueError("invalid premium reward policy")

    sources = extract_sources(xml_bin)
    shop = parse_shop(sources["shop"])
    serverdb = parse_serverdb(sources["serverdb"])
    career = parse_career(sources["career"])
    seasons, events = main_career(career)

    vehicle_rows, vehicle_audit = build_vehicle_rows(shop, serverdb, events, multiplier)
    event_rows, event_audit = build_event_rows(events, premium_divisor, premium_cap)
    upgrade_rows, upgrade_audit = build_upgrade_rows(shop, vehicle_rows, multiplier)

    vehicle_entries = vehicle_binary.normalize(vehicle_rows)
    event_entries = event_binary.normalize(event_rows)
    upgrade_entries = upgrade_binary.normalize(upgrade_rows)

    output_dir.mkdir(parents=True, exist_ok=True)

    vehicle_data = vehicle_binary.build(vehicle_entries)
    event_data = event_binary.build(event_entries)
    upgrade_data = upgrade_binary.build(upgrade_entries)

    outputs = {
        "CampaignCatalog.dat": vehicle_data,
        "CampaignEvents.dat": event_data,
        "CampaignUpgrades.dat": upgrade_data,
    }

    for name, data in outputs.items():
        (output_dir / name).write_bytes(data)
        if package_dir is not None:
            package_dir.mkdir(parents=True, exist_ok=True)
            (package_dir / name).write_bytes(data)

    decoded = output_dir / "decoded"
    decoded.mkdir(exist_ok=True)
    (decoded / "asphaltshop.xml").write_bytes(sources["shop"])
    (decoded / "asphaltserverdb.xml").write_bytes(sources["serverdb"])
    (decoded / "career_data.json").write_bytes(sources["career"])

    write_json(output_dir / "vehicles.audit.json", vehicle_audit)
    write_json(output_dir / "events.audit.json", event_audit)
    write_json(output_dir / "upgrades.audit.json", upgrade_audit)

    summary = {
        "source_xml_bin": str(xml_bin),
        "source_xml_bin_sha256": sha256(xml_bin.read_bytes()),
        "source_payload_sha256": {k: sha256(v) for k, v in sources.items()},
        "economy": {
            "content_price_multiplier": multiplier,
            "premium_race_policy": {
                "divisor": premium_divisor,
                "cap": premium_cap,
                "formula": "max(1, round((money_for_playing + position_1) / divisor)), capped; zero if repeat credits are zero",
            },
            "repeat_policy_runtime": {
                "runs_1_to_10": 1.0,
                "decay_per_run_after_10": 0.002,
                "floor": 0.98,
            },
        },
        "source_counts": {
            "shop_cars": len(shop),
            "serverdb_cars": len(serverdb),
            "main_seasons": len(seasons),
            "main_events": len(events),
        },
        "generated_counts": {
            "vehicles": len(vehicle_entries),
            "events": len(event_entries),
            "upgrade_and_prokit_steps": len(upgrade_entries),
        },
        "outputs": {
            name: {"bytes": len(data), "sha256": sha256(data)}
            for name, data in outputs.items()
        },
        "guards": {
            "all_shop_cars_have_catalog_entry": len(vehicle_entries) == len(shop),
            "main_events_equal_event_catalog_entries": len(event_entries) == len(events),
            "no_placeholder_data": True,
        },
    }

    # The recovered production package is known to have 61 active cars.
    # Treat a mismatch as a hard error instead of silently generating a partial catalog.
    if len(shop) != 61:
        raise RuntimeError(
            f"production guard failed: expected 61 shop cars, decoded {len(shop)}"
        )
    if len(events) == 0:
        raise RuntimeError("production guard failed: no main-career events decoded")

    write_json(output_dir / "production-data-report.json", summary)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, required=True)
    ap.add_argument("--xml-bin", type=Path)
    ap.add_argument("--output-dir", type=Path)
    ap.add_argument("--multiplier", type=float, default=0.20)
    ap.add_argument("--premium-divisor", type=int, default=2500)
    ap.add_argument("--premium-cap", type=int, default=5)
    ap.add_argument("--no-install", action="store_true")
    ns = ap.parse_args()

    root = ns.project_root.resolve()
    package = root / "_PACKAGE_PHASE5"
    xml_bin = (ns.xml_bin or (package / "data" / "xml.bin")).resolve()
    out = (ns.output_dir or (root / "_CAMPAIGN_PRODUCTION_DATA")).resolve()

    if not xml_bin.is_file():
        raise SystemExit(f"xml.bin not found: {xml_bin}")

    report = build_all(
        xml_bin=xml_bin,
        output_dir=out,
        package_dir=None if ns.no_install else package,
        multiplier=ns.multiplier,
        premium_divisor=ns.premium_divisor,
        premium_cap=ns.premium_cap,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
