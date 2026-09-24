#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

MAGIC = 0x53535852
VERSION = 1
MAX_OFFERS = 512

CURRENCY = {
    "credits": 1,
    "premium": 2,
    "free": 3,
}

ENTRY = struct.Struct("<8i")
HEADER = struct.Struct("<4I")
CHECKSUM = struct.Struct("<I")


def fnv1a(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def offer_key_hash(key: str) -> int:
    raw = key.encode("utf-8")
    if not raw or len(raw) > 512 or b"\\x00" in raw:
        raise ValueError("offer_key must be 1..512 UTF-8 bytes without NUL")
    h = fnv1a(raw) & 0x7FFFFFFF
    return h or 1


def load(path: Path) -> list[dict]:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if int(obj.get("schema", 0)) != 1:
        raise ValueError("expected schema=1")
    offers = list(obj.get("offers", []))
    if len(offers) > MAX_OFFERS:
        raise ValueError(f"too many offers: {len(offers)} > {MAX_OFFERS}")
    return offers


def encode(offers: list[dict]) -> bytes:
    rows = []
    seen = set()

    for raw in offers:
        if "offer_key" in raw:
            offer_id = offer_key_hash(str(raw["offer_key"]))
        else:
            offer_id = int(raw["offer_id"])
        item_id = int(raw["item_id"])
        quantity = int(raw["quantity"])
        currency_name = str(raw["currency"]).lower()
        if currency_name not in CURRENCY:
            raise ValueError(f"unknown currency {currency_name!r}")

        currency_type = CURRENCY[currency_name]
        price = int(raw.get("price", 0))
        unlock_node_id = int(raw.get("unlock_node_id", 0))
        flags = int(raw.get("flags", 0))

        if offer_id <= 0 or item_id <= 0 or quantity <= 0:
            raise ValueError("offer_id, item_id and quantity must be positive")
        if price < 0 or unlock_node_id < 0:
            raise ValueError("price and unlock_node_id must be non-negative")
        if currency_type == CURRENCY["free"] and price != 0:
            raise ValueError("free offers must have price=0")
        if offer_id in seen:
            raise ValueError(f"duplicate/colliding offer_id {offer_id}")
        seen.add(offer_id)

        rows.append((
            offer_id, item_id, quantity, currency_type,
            price, unlock_node_id, flags, 0
        ))

    rows.sort(key=lambda x: x[0])

    buf = bytearray()
    buf += HEADER.pack(MAGIC, VERSION, len(rows), 0)
    for row in rows:
        buf += ENTRY.pack(*row)
    for _ in range(MAX_OFFERS - len(rows)):
        buf += ENTRY.pack(0, 0, 0, 0, 0, 0, 0, 0)

    buf += CHECKSUM.pack(fnv1a(buf))
    return bytes(buf)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build CampaignStore.dat")
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ns = ap.parse_args()

    data = encode(load(ns.input))
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_bytes(data)
    print(f"wrote {ns.output} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
