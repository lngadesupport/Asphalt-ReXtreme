#!/usr/bin/env python3
"""Simulate mandatory-car progression using ReXtreme Premium currency rules."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from economy_audit import FILTERS


def load(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def one_time_credit_rewards(event: dict) -> int:
    total = 0
    for prefix in ("first_star_reward", "second_star_reward", "third_star_reward", "completion_reward"):
        if str(event.get(prefix + "_type", "")).lower() == "credits":
            total += int(event.get(prefix + "_amount", 0) or 0)
    return total


def repeat_payout(event: dict) -> int:
    return int(event.get("money_for_playing", 0) or 0) + int(event.get("position_1", 0) or 0)


def discounted(value: int, multiplier: float) -> int:
    return max(0, int(round(value * multiplier)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("career_data", type=Path)
    ap.add_argument("car_catalog", type=Path)
    ap.add_argument("--vehicle-multiplier", type=float, default=0.80)
    ap.add_argument("--premium-currency-race-multiplier", type=float, default=0.50)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    career = load(args.career_data)
    cars = load(args.car_catalog)
    by_id = {int(car["car_id"]): car for car in cars}

    seasons = sorted(
        [s for s in career["seasons"] if int(s.get("serieid", 0) or 0) == 1],
        key=lambda s: int(s.get("index", 0) or 0),
    )

    credits = 0
    premium = 0
    owned: set[int] = set()
    prior_repeat_payouts: list[int] = []
    gates: list[dict] = []
    total_extra_repeats = 0
    max_extra_repeats = 0

    def farm(repeats: int, best_repeat: int) -> None:
        nonlocal credits, premium
        if repeats <= 0 or best_repeat <= 0:
            return
        credits += repeats * best_repeat
        premium += repeats * math.floor(
            best_repeat * args.premium_currency_race_multiplier
        )

    for season in seasons:
        season_id = int(season.get("seasonid", season.get("id", 0)) or 0)
        events = sorted(
            [
                e
                for e in career["events"]
                if int(e.get("season", 0) or 0) == season_id
                and not e.get("masteries", False)
            ],
            key=lambda e: int(e.get("eventid", 0) or 0),
        )

        for event in events:
            car_filter = str(event.get("carracerfilter", "") or "")
            car_id = FILTERS.get(car_filter)

            if car_id is not None and car_id not in owned:
                car = by_id[car_id]
                credit_price = int(car.get("credit_price", 0) or 0)
                premium_price = int(car.get("hardcurrency_price", 0) or 0)

                if credit_price > 0:
                    currency = "credits"
                    price = discounted(credit_price, args.vehicle_multiplier)
                    wallet_before = credits
                elif premium_price > 0:
                    currency = "premium"
                    price = discounted(premium_price, args.vehicle_multiplier)
                    wallet_before = premium
                else:
                    currency = "none"
                    price = 0
                    wallet_before = 0

                best_repeat = max(prior_repeat_payouts, default=0)
                best_repeat_premium = math.floor(
                    best_repeat * args.premium_currency_race_multiplier
                )

                if currency == "credits":
                    per_repeat = best_repeat
                    missing = max(0, price - credits)
                elif currency == "premium":
                    per_repeat = best_repeat_premium
                    missing = max(0, price - premium)
                else:
                    per_repeat = 0
                    missing = 0

                repeats = 0
                if missing > 0:
                    if per_repeat <= 0:
                        repeats = -1
                    else:
                        repeats = math.ceil(missing / per_repeat)
                        farm(repeats, best_repeat)

                if currency == "credits" and repeats != -1:
                    credits -= price
                elif currency == "premium" and repeats != -1:
                    premium -= price

                if repeats > 0:
                    total_extra_repeats += repeats
                    max_extra_repeats = max(max_extra_repeats, repeats)

                owned.add(car_id)
                gates.append(
                    {
                        "event_id": int(event["eventid"]),
                        "car_id": car_id,
                        "class": car.get("class", ""),
                        "purchase_currency": currency,
                        "original_credit_price": credit_price,
                        "original_premium_price": premium_price,
                        "rextreme_price": price,
                        "wallet_before": wallet_before,
                        "best_prior_repeat_credits": best_repeat,
                        "best_prior_repeat_premium": best_repeat_premium,
                        "extra_repeats_needed": repeats,
                        "credits_after_purchase": credits,
                        "premium_after_purchase": premium,
                    }
                )

            repeat = repeat_payout(event)
            credits += repeat + one_time_credit_rewards(event)
            premium += math.floor(
                repeat * args.premium_currency_race_multiplier
            )
            prior_repeat_payouts.append(repeat)

        for reward in season.get("rewards", []) or []:
            reward_type = str(reward.get("completionrewardtype", "")).lower()
            amount = int(reward.get("completionrewardamount", 0) or 0)
            if reward_type == "credits":
                credits += amount
            elif reward_type == "hardcurrency":
                premium += amount

    blocked = [g for g in gates if g["extra_repeats_needed"] == -1]
    result = {
        "vehicle_multiplier": args.vehicle_multiplier,
        "premium_currency_race_multiplier": args.premium_currency_race_multiplier,
        "mandatory_cars": len(owned),
        "total_extra_repeats": total_extra_repeats,
        "max_extra_repeats_at_one_gate": max_extra_repeats,
        "blocked_gates": len(blocked),
        "final_credits": credits,
        "final_premium_currency": premium,
        "gates": gates,
    }

    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "gates"},
            indent=2,
            ensure_ascii=False,
        )
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
