#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from build_campaign_vehicle_catalog import encode as encode_catalog
from rextreme_economy import parse_shop, parse_serverdb

SHOP_MARKER = b"<AsphaltShopConfiguration"
SERVERDB_MARKER = b'k_2206374417="'

DEFAULT_RANGES = {
    "D": (25000, 75000),
    "C": (150000, 300000),
    "B": (500000, 800000),
    "A": (1200000, 2000000),
    "S": (3000000, 4500000),
}
DEFAULT_TOKEN_TARGET = {
    "B": 500,
    "A": 1500,
    "S": 3500,
}


def contains_marker(path: Path, marker: bytes) -> bool:
    try:
        with path.open("rb") as f:
            carry = b""
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    return False
                data = carry + chunk
                if marker in data:
                    return True
                carry = data[-max(0, len(marker) - 1):]
    except (OSError, PermissionError):
        return False


def discover(root: Path, marker: bytes) -> list[Path]:
    hits: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size <= 0:
                continue
        except OSError:
            continue
        if contains_marker(path, marker):
            hits.append(path)
    return hits


def scale(value: float, vmin: float, vmax: float, out_min: int, out_max: int) -> int:
    if vmax <= vmin:
        return out_min
    t = (value - vmin) / (vmax - vmin)
    t = max(0.0, min(1.0, t))
    return int(round(out_min + t * (out_max - out_min)))


def load_policy(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_rows(shop: dict[int, dict], defs: dict[int, dict], policy: dict) -> list[dict]:
    ranges = dict(DEFAULT_RANGES)
    token_targets = dict(DEFAULT_TOKEN_TARGET)

    vp = policy.get("vehicle_prices", {}) if isinstance(policy, dict) else {}
    for cls, values in vp.items():
        if cls not in ranges or not isinstance(values, dict):
            continue
        lo = values.get("credits_min")
        hi = values.get("credits_max")
        if lo is not None:
            ranges[cls] = (int(lo), int(hi if hi is not None else max(int(lo), ranges[cls][1])))
        token = values.get("token_price")
        if token is not None:
            token_targets[cls] = int(token)
        token_min = values.get("token_price_min")
        if token_min is not None:
            token_targets[cls] = int(token_min)

    by_class: dict[str, list[tuple[int, float]]] = {}
    for car_id in shop:
        d = defs.get(car_id, {})
        cls = str(d.get("class", "")).upper()
        rank = float(d.get("base_rank", 0) or 0)
        by_class.setdefault(cls, []).append((car_id, rank))

    class_bounds = {}
    for cls, rows in by_class.items():
        ranks = [r for _, r in rows]
        class_bounds[cls] = (min(ranks) if ranks else 0, max(ranks) if ranks else 0)

    result: list[dict] = []
    for car_id in sorted(shop):
        s = shop[car_id]
        d = defs.get(car_id, {})
        cls = str(d.get("class", "")).upper()
        rank = float(d.get("base_rank", 0) or 0)
        credits = int(s.get("credit_price", 0) or 0)
        premium = int(s.get("hardcurrency_price", 0) or 0)

        if credits <= 0 and premium <= 0:
            acq = "free"
            cost = 0
        elif credits > 0:
            # Preserve original intra-class order but use the Campaign class range.
            lo, hi = ranges.get(cls, (max(1, int(round(credits * 0.20))), max(1, int(round(credits * 0.20)))))
            rmin, rmax = class_bounds.get(cls, (rank, rank))
            acq = "credits"
            cost = max(1, scale(rank, rmin, rmax, lo, hi))
        elif cls in ("D", "C"):
            # Early classes are always obtainable with farmable credits.
            lo, hi = ranges.get(cls, (25000, 300000))
            rmin, rmax = class_bounds.get(cls, (rank, rank))
            acq = "credits"
            cost = max(1, scale(rank, rmin, rmax, lo, hi))
        else:
            # Higher-class premium currency remains gameplay-earned, never IAP-only.
            acq = "premium"
            target = token_targets.get(cls)
            cost = max(1, target if target is not None else int(round(premium * 0.20)))

        class_id = {"D": 1, "C": 2, "B": 3, "A": 4, "S": 5}.get(cls, 0)
        result.append({
            "car_id": car_id,
            "acquisition_type": acq,
            "item_id": 0,
            "cost": cost,
            "unlock_node_id": 0,
            "class_id": class_id,
            "flags": 0,
        })

    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Build CampaignCatalog.dat directly from an extracted package")
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--policy", type=Path, default=None)
    ap.add_argument("--report", type=Path, default=None)
    ns = ap.parse_args()

    package = ns.package.resolve()
    if not package.is_dir():
        raise SystemExit(f"package directory not found: {package}")

    shops = discover(package, SHOP_MARKER)
    dbs = discover(package, SERVERDB_MARKER)

    if len(shops) != 1:
        raise SystemExit(f"expected exactly one AsphaltShopConfiguration source, found {len(shops)}: {shops}")
    if len(dbs) != 1:
        raise SystemExit(f"expected exactly one car definition database, found {len(dbs)}: {dbs}")

    shop = parse_shop(shops[0])
    defs = parse_serverdb(dbs[0])
    if not shop:
        raise SystemExit("shop parser returned zero cars")

    missing_defs = sorted(set(shop) - set(defs))
    policy = load_policy(ns.policy)
    rows = build_rows(shop, defs, policy)

    payload = {"schema": 1, "vehicles": rows}
    binary = encode_catalog(rows)

    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_bytes(binary)

    report = {
        "shop_source": str(shops[0]),
        "definition_source": str(dbs[0]),
        "vehicle_count": len(rows),
        "missing_definition_ids": missing_defs,
        "output": str(ns.output),
        "policy": str(ns.policy) if ns.policy else None,
        "vehicles": rows,
    }

    report_path = ns.report or ns.output.with_suffix(".json")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "vehicle_count": len(rows),
        "shop_source": str(shops[0]),
        "definition_source": str(dbs[0]),
        "output": str(ns.output),
        "report": str(report_path),
        "missing_definition_count": len(missing_defs),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
