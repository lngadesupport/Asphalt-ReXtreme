#!/usr/bin/env python3
"""Analyze decrypted Asphalt Xtreme 1.7.3.8 economy/career data."""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

CARDEF_RE = re.compile(
    r'k_2206374417="([^"]+)"'
    r'[^>]*?k_4250631189="(\d+)"'
    r'[^>]*?k_1571869371="([^"]+)"'
    r'[^>]*?k_1914113855="([^"]+)"'
)


def campaign_price(original: int, multiplier: float = 0.20) -> int:
    """80% discount: player pays 20% of the original content price."""
    return max(0, int(round(original * multiplier)))


def repeat_reward_multiplier(
    repeat_count: int,
    grace_runs: int = 10,
    decay_per_run: float = 0.002,
    floor: float = 0.98,
) -> float:
    """Campaign Edition repeat rule.

    Runs 1..grace_runs pay 100%. Each run after that loses 0.2 percentage
    points by default, with a hard floor of 98%.
    """
    if repeat_count <= grace_runs:
        return 1.0
    return max(floor, 1.0 - (repeat_count - grace_runs) * decay_per_run)


def first_xml_document(text: str, root_name: str) -> str:
    end_tag = f"</{root_name}>"
    end = text.find(end_tag)
    if end < 0:
        raise ValueError(f"Could not find {end_tag}")
    return text[:end + len(end_tag)]


def parse_shop(path: Path) -> dict[int, dict]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    root = ET.fromstring(first_xml_document(text, "AsphaltShopConfiguration"))

    result: dict[int, dict] = {}
    for car in root.findall("./Car"):
        car_id = int(car.get("carId"))
        base = {"credits": 0, "hardcurrency": 0}
        upgrades = {"credits": [], "hardcurrency": []}

        price_root = car.find("./UpgradePrices")
        if price_root is not None:
            for price in price_root.findall("./Price"):
                if price.get("Id") == "CAR_PRICE":
                    currency = price.get("Currency", "").lower()
                    if currency in base:
                        base[currency] = int(float(price.get("Price", "0")))

        prokit = car.find("./ProKitPrices")
        if prokit is not None:
            for price in prokit.findall("./Price"):
                currency = price.get("Currency", "").lower()
                if currency in upgrades:
                    upgrades[currency].append(int(float(price.get("Price", "0"))))

        result[car_id] = {
            "car_id": car_id,
            "credit_price": base["credits"],
            "hardcurrency_price": base["hardcurrency"],
            "upgrade_credit_total": sum(upgrades["credits"]),
            "upgrade_hardcurrency_total": sum(upgrades["hardcurrency"]),
        }

    return result


def parse_serverdb(path: Path) -> dict[int, dict]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    result = {}
    for car_def, car_id, car_class, rank in CARDEF_RE.findall(text):
        result[int(car_id)] = {
            "car_def": car_def,
            "class": car_class,
            "base_rank": float(rank) if "." in rank else int(rank),
        }
    return result


def parse_career(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def analyze(shop_path: Path, serverdb_path: Path, career_path: Path, output: Path, multiplier: float) -> None:
    shop = parse_shop(shop_path)
    definitions = parse_serverdb(serverdb_path)
    career = parse_career(career_path)

    vehicle_rows = []
    pricing_counts = defaultdict(int)
    dual_ratios: dict[str, list[float]] = defaultdict(list)

    for car_id in sorted(shop):
        shop_car = shop[car_id]
        definition = definitions.get(car_id, {})
        credits = shop_car["credit_price"]
        hardcurrency = shop_car["hardcurrency_price"]

        if credits > 0 and hardcurrency > 0:
            pricing_mode = "dual"
            dual_ratios[definition.get("class", "?")].append(credits / hardcurrency)
        elif credits > 0:
            pricing_mode = "credits_only"
        elif hardcurrency > 0:
            pricing_mode = "hardcurrency_only"
        else:
            pricing_mode = "free"

        pricing_counts[pricing_mode] += 1

        vehicle_rows.append({
            "car_id": car_id,
            "car_def": definition.get("car_def", ""),
            "class": definition.get("class", ""),
            "base_rank": definition.get("base_rank", ""),
            "pricing_mode": pricing_mode,
            "original_credits": credits,
            "original_hardcurrency": hardcurrency,
            "campaign_credits_20pct": campaign_price(credits, multiplier) if credits > 0 else "",
            "token_only_credit_conversion": "TBD" if credits == 0 and hardcurrency > 0 else "",
            "upgrade_credit_total_original": shop_car["upgrade_credit_total"],
            "upgrade_hardcurrency_total_original": shop_car["upgrade_hardcurrency_total"],
        })

    write_csv(output / "cars.csv", vehicle_rows, list(vehicle_rows[0].keys()))

    seasons = {int(item.get("seasonid", item.get("id"))): item for item in career["seasons"]}
    event_rows = []
    season_aggregation = defaultdict(lambda: {"events": 0, "repeat_first": [], "star_credits": 0})

    for event in career["events"]:
        season_id = int(event.get("season", 0))
        season = seasons.get(season_id, {})
        repeat_first = int(event.get("money_for_playing", 0) or 0) + int(event.get("position_1", 0) or 0)

        star_credits = 0
        for prefix in ("first", "second", "third"):
            if str(event.get(f"{prefix}_star_reward_type", "")).lower() == "credits":
                star_credits += int(event.get(f"{prefix}_star_reward_amount", 0) or 0)

        row = {
            "event_id": event.get("eventid", event.get("id")),
            "season": season_id,
            "class": season.get("carclass", ""),
            "rank_requirement": event.get("rank", 0),
            "unlock_event_id": event.get("unlockeventid", 0),
            "money_for_playing": event.get("money_for_playing", 0),
            "position_1": event.get("position_1", 0),
            "position_2": event.get("position_2", 0),
            "position_3": event.get("position_3", 0),
            "repeat_first_place_candidate": repeat_first,
            "repeat_run_11_multiplier": repeat_reward_multiplier(11),
            "repeat_run_20_multiplier": repeat_reward_multiplier(20),
            "repeat_floor_multiplier": repeat_reward_multiplier(999999),
            "one_time_star_credits": star_credits,
            "completion_reward_type": event.get("completion_reward_type", ""),
            "completion_reward_amount": event.get("completion_reward_amount", 0),
            "car_filter": event.get("carracerfilter", ""),
            "event_def": event.get("event_def", ""),
        }
        event_rows.append(row)

        aggregate = season_aggregation[season_id]
        aggregate["events"] += 1
        aggregate["repeat_first"].append(repeat_first)
        aggregate["star_credits"] += star_credits

    write_csv(output / "career_events.csv", event_rows, list(event_rows[0].keys()))

    season_rows = []
    for season_id in sorted(seasons):
        season = seasons[season_id]
        aggregate = season_aggregation[season_id]

        completion_credits = 0
        completion_hardcurrency = 0
        for reward in season.get("rewards", []):
            reward_type = str(reward.get("completionrewardtype", "")).lower()
            amount = int(reward.get("completionrewardamount", 0) or 0)
            if reward_type == "credits":
                completion_credits += amount
            elif reward_type == "hardcurrency":
                completion_hardcurrency += amount

        repeat_values = aggregate["repeat_first"]
        season_rows.append({
            "season": season_id,
            "class": season.get("carclass", ""),
            "events": aggregate["events"],
            "repeat_first_place_avg": round(sum(repeat_values) / len(repeat_values), 2) if repeat_values else 0,
            "repeat_first_place_min": min(repeat_values) if repeat_values else 0,
            "repeat_first_place_max": max(repeat_values) if repeat_values else 0,
            "one_time_star_credits_total": aggregate["star_credits"],
            "season_completion_credits": completion_credits,
            "season_completion_hardcurrency": completion_hardcurrency,
            "unlock_event_id": season.get("unlockeventid", 0),
        })

    write_csv(output / "seasons.csv", season_rows, list(season_rows[0].keys()))

    ratio_summary = {}
    all_ratios = []
    for car_class, ratios in dual_ratios.items():
        if not ratios:
            continue
        all_ratios.extend(ratios)
        ratio_summary[car_class] = {
            "count": len(ratios),
            "median_credits_per_token": round(statistics.median(ratios), 2),
            "min": round(min(ratios), 2),
            "max": round(max(ratios), 2),
        }

    summary = {
        "vehicle_count": len(vehicle_rows),
        "pricing_modes": dict(pricing_counts),
        "shop_content_price_multiplier": multiplier,
        "career_event_count": len(event_rows),
        "season_count": len(season_rows),
        "repeat_reward_rule": {
            "grace_runs": 10,
            "decay_per_run": 0.002,
            "floor": 0.98,
        },
        "dual_price_credit_per_token_by_class": ratio_summary,
        "dual_price_credit_per_token_overall_median": round(statistics.median(all_ratios), 2) if all_ratios else None,
        "note": (
            "Hardcurrency-only vehicle conversion remains data-driven. "
            "Campaign Edition removes real-money acquisition but preserves "
            "premium currency as an earnable race reward."
        ),
    }

    output.mkdir(parents=True, exist_ok=True)
    (output / "economy_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Asphalt ReXtreme Campaign Edition economy data")
    parser.add_argument("--shop", type=Path, required=True)
    parser.add_argument("--serverdb", type=Path, required=True)
    parser.add_argument("--career", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("economy-analysis"))
    parser.add_argument("--vehicle-multiplier", type=float, default=0.20)
    args = parser.parse_args()

    if not 0 < args.vehicle_multiplier <= 1:
        raise SystemExit("vehicle multiplier must be greater than 0 and <= 1")

    analyze(args.shop, args.serverdb, args.career, args.out, args.vehicle_multiplier)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
