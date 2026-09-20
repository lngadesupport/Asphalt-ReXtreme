#!/usr/bin/env python3
"""Audit decoded xml.bin data for ReXtreme offline/economy gates.

The tool reads the user's own xml.bin, decodes XTEA streams in memory and
emits only metadata/snippets needed to identify deterministic transforms.
It does not export full proprietary plaintext unless --extract is requested.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

try:
    from tools import xtea_assets
except ModuleNotFoundError:  # direct script execution from tools/
    import xtea_assets


TERMS = {
    "energy": (
        "energy", "fuel", "refill", "recharge",
    ),
    "maintenance": (
        "maintenance", "repaircost", "repair_cost", "durability",
    ),
    "fuses": (
        "fuse", "fuses",
    ),
    "iap": (
        "iap", "inapp", "in-app", "purchase", "hardcurrency", "cashshop",
    ),
    "ads": (
        "ad_reward", "adreward", "rewarded", "advert", "vungle",
    ),
    "sync": (
        "full_sync", "partial_sync", "sync.php", "server_sync", "cloud",
    ),
    "caps": (
        "daily", "cooldown", "limit", "creditsEarnedToday",
        "DoubleCreditsLimit", "DoubleCreditsRaceLimit",
    ),
    "social": (
        "facebook", "msn", "social", "sns",
    ),
    "online": (
        "gameloft", "http://", "https://", "server", "online",
    ),
}


def text_payload(payload: bytes) -> str | None:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            text = payload.decode(encoding)
        except UnicodeDecodeError:
            continue
        stripped = text.lstrip()
        if stripped.startswith(("<", "{", "[")):
            return text
    return None


def compact_snippet(text: str, start: int, end: int, radius: int = 100) -> str:
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    snippet = text[lo:hi]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:280]


def audit(xml_bin: Path, extract: Path | None = None) -> dict:
    rows: list[dict] = []
    totals: Counter[str] = Counter()
    decoded = 0
    text_entries = 0

    if extract is not None:
        extract.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(xml_bin) as archive:
        for info in archive.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".xtea"):
                continue

            row = {
                "entry": info.filename,
                "stored_size": info.file_size,
                "categories": {},
                "matches": [],
            }

            try:
                payload, meta = xtea_assets.decode_stream(archive.read(info.filename))
            except xtea_assets.DecodeError as exc:
                row["decode_error"] = str(exc)
                rows.append(row)
                continue

            decoded += 1
            row["stream_type"] = meta.get("stream_type")
            row["payload_size"] = len(payload)

            text = text_payload(payload)
            if text is None:
                row["text"] = False
                rows.append(row)
                continue

            text_entries += 1
            row["text"] = True
            lower = text.lower()

            for category, needles in TERMS.items():
                count = 0
                seen_snippets: set[str] = set()
                for needle in needles:
                    pos = 0
                    needle_lower = needle.lower()
                    while True:
                        idx = lower.find(needle_lower, pos)
                        if idx < 0:
                            break
                        count += 1
                        if len(seen_snippets) < 5:
                            snippet = compact_snippet(text, idx, idx + len(needle))
                            if snippet not in seen_snippets:
                                seen_snippets.add(snippet)
                                row["matches"].append(
                                    {
                                        "category": category,
                                        "term": needle,
                                        "snippet": snippet,
                                    }
                                )
                        pos = idx + max(1, len(needle_lower))

                if count:
                    row["categories"][category] = count
                    totals[category] += count

            if extract is not None:
                target = extract / Path(info.filename).with_suffix("")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
                row["extracted_to"] = str(target)

            if row["categories"]:
                rows.append(row)

    return {
        "xml_bin": str(xml_bin),
        "decoded_xtea_entries": decoded,
        "text_entries": text_entries,
        "category_totals": dict(sorted(totals.items())),
        "candidate_entries": len(rows),
        "entries": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("xml_bin", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--extract",
        type=Path,
        help="Optional private output directory for complete decoded plaintext.",
    )
    args = ap.parse_args()

    try:
        report = audit(
            args.xml_bin.resolve(),
            args.extract.resolve() if args.extract else None,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except (OSError, zipfile.BadZipFile, xtea_assets.DecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({
        "decoded_xtea_entries": report["decoded_xtea_entries"],
        "text_entries": report["text_entries"],
        "candidate_entries": report["candidate_entries"],
        "category_totals": report["category_totals"],
        "report": str(args.out),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
