#!/usr/bin/env python3
"""Campaign Edition shop-price rebalance helper.

The user pays 20% of the original content price (80% discount).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def rounded_price(value: int, multiplier: float) -> int:
    return max(0, int(round(value * multiplier)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="JSON array/object containing original prices")
    ap.add_argument("output", type=Path)
    ap.add_argument("--multiplier", type=float, default=0.20)
    args = ap.parse_args()

    if not 0 < args.multiplier <= 1:
        raise SystemExit("Multiplier must be > 0 and <= 1.")

    data = json.loads(args.input.read_text(encoding="utf-8"))
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict) and isinstance(data.get("vehicles"), list):
        records = data["vehicles"]
    else:
        raise SystemExit("Expected a JSON list or an object with a vehicles list.")

    out = []
    for item in records:
        row = dict(item)
        original = int(row["price"])
        row["original_price"] = original
        row["campaign_price"] = rounded_price(original, args.multiplier)
        row["price_multiplier"] = args.multiplier
        row["discount_fraction"] = 1.0 - args.multiplier
        out.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"vehicles": out}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(out)} vehicles to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
