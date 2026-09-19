#!/usr/bin/env python3
"""
Asphalt ReXtreme economy helper.

Reads a simple JSON export of vehicle prices and produces Premium-mode prices
using the project's baseline 20% reduction. It is intentionally data-agnostic:
real game values must be extracted from build 1.7.3.8 before use.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def rounded_price(value: int, multiplier: float) -> int:
    # ReXtreme Premium requirement: apply the multiplier exactly and only
    # round to a whole credit. Do not add price-tier rounding that would
    # change the agreed percentage reduction.
    return max(0, int(round(value * multiplier)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="JSON array/object containing original vehicle prices")
    ap.add_argument("output", type=Path)
    ap.add_argument("--multiplier", type=float, default=0.80)
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
        row["premium_price"] = rounded_price(original, args.multiplier)
        row["price_multiplier"] = args.multiplier
        out.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"vehicles": out}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(out)} vehicles to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
