#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ASCII = re.compile(rb"[\x20-\x7e]{3,256}")
KEY_TOKEN = re.compile(r"^[A-Za-z0-9_./:-]{2,160}$")

MARKERS = (
    b"scripts/general/buy_item.php",
    b"item=",
    b"OnlinePurchaseRequest",
)

# Names strongly associated with locally purchasable content. This is discovery
# only; no inferred entry becomes a runtime offer automatically.
HINTS = (
    "booster", "boost", "prokit", "pro_kit", "blueprint", "pack", "box",
    "card", "decal", "ticket", "fuel", "energy", "material", "part"
)


def strings(path: Path):
    data = path.read_bytes()
    for m in ASCII.finditer(data):
        yield m.start(), m.group().decode("ascii", "ignore")


def score(value: str) -> int:
    low = value.lower()
    s = 0
    for hint in HINTS:
        if hint in low:
            s += 2
    if "/" not in value and "\\" not in value:
        s += 1
    if "." not in value:
        s += 1
    if 3 <= len(value) <= 80:
        s += 1
    return s


def scan_file(path: Path, root: Path):
    try:
        data = path.read_bytes()
    except OSError:
        return None

    marker_hits = [m.decode("ascii", "ignore") for m in MARKERS if m in data]
    if not marker_hits:
        return None

    candidates = []
    for off, value in strings(path):
        if not KEY_TOKEN.fullmatch(value):
            continue
        low = value.lower()
        if value.startswith("http") or value.startswith("scripts/"):
            continue
        sc = score(value)
        if sc < 3:
            continue
        candidates.append({
            "offset": off,
            "value": value,
            "score": sc,
        })

    # Stable, deduplicated by textual key.
    seen = set()
    unique = []
    for row in sorted(candidates, key=lambda x: (-x["score"], x["value"], x["offset"])):
        if row["value"] in seen:
            continue
        seen.add(row["value"])
        unique.append(row)

    return {
        "file": path.relative_to(root).as_posix(),
        "markers": marker_hits,
        "candidates": unique[:500],
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit extracted package for legacy local shop item keys"
    )
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ns = ap.parse_args()

    root = ns.package.resolve()
    if not root.is_dir():
        raise SystemExit(f"package directory not found: {root}")

    files = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        try:
            if path.stat().st_size > 128 * 1024 * 1024:
                continue
        except OSError:
            continue
        row = scan_file(path, root)
        if row:
            files.append(row)

    all_keys = {}
    for f in files:
        for c in f["candidates"]:
            key = c["value"]
            current = all_keys.get(key)
            entry = {
                "offer_key": key,
                "best_score": c["score"],
                "source_file": f["file"],
                "source_offset": c["offset"],
            }
            if current is None or entry["best_score"] > current["best_score"]:
                all_keys[key] = entry

    report = {
        "package": str(root),
        "files_with_purchase_markers": len(files),
        "candidate_key_count": len(all_keys),
        "candidate_keys": sorted(
            all_keys.values(),
            key=lambda x: (-x["best_score"], x["offer_key"])
        ),
        "files": files,
        "note": (
            "Discovery only. No candidate is automatically a CampaignStore offer. "
            "Quantity, item_id and local price must be backed by verified package data "
            "or an explicit Campaign Edition rule."
        ),
    }

    ns.report.parent.mkdir(parents=True, exist_ok=True)
    ns.report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps({
        "files_with_purchase_markers": len(files),
        "candidate_key_count": len(all_keys),
        "report": str(ns.report),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
