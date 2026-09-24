#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from xtea_assets import decode_stream
from rextreme_economy import first_xml_document
import build_campaign_store_catalog as store_binary

KEY_ATTRS = {
    "id", "name", "key", "item", "itemid", "item_id",
    "product", "productid", "product_id", "sku", "offer", "offerid", "offer_id",
}
QTY_ATTRS = {"quantity", "qty", "amount", "count", "pieces"}
LOCAL_CURRENCY = {
    "credits": "credits",
    "hardcurrency": "premium",
}
REAL_MONEY_HINTS = (
    "iap", "realmoney", "real_money", "cashpack", "cash_pack",
    "currency_pack", "hardcurrency_pack", "credits_pack", "credit_pack",
    "bundle_money", "microsoft_store",
)
GENERIC_PRICE_IDS = {
    "", "price", "default", "car_price", "upgrade_price", "prokit_price"
}


def norm(s: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")


def hash31(text: str) -> int:
    return store_binary.offer_key_hash(text)


def decode_shop(xml_bin: Path) -> bytes:
    with zipfile.ZipFile(xml_bin, "r") as z:
        candidates = [
            i for i in z.infolist()
            if not i.is_dir() and Path(i.filename).name.lower() == "asphaltshop.xtea"
        ]
        if len(candidates) != 1:
            raise RuntimeError(f"expected one asphaltshop.xtea, found {len(candidates)}")
        payload, _ = decode_stream(z.read(candidates[0]))
        return payload


def get_quantity(elem: ET.Element) -> int:
    for k, v in elem.attrib.items():
        if norm(k) in QTY_ATTRS:
            try:
                n = int(float(v))
            except (TypeError, ValueError):
                continue
            if n > 0:
                return n
    return 1


def element_keys(elem: ET.Element, prices: list[ET.Element]) -> list[str]:
    keys = []
    for k, v in elem.attrib.items():
        nk = norm(k)
        value = str(v).strip()
        if nk in KEY_ATTRS and value:
            keys.append(value)

    for p in prices:
        pid = str(p.get("Id", "") or p.get("id", "")).strip()
        if pid and norm(pid) not in GENERIC_PRICE_IDS:
            keys.append(pid)

    # Stable textual tag is only useful when it is specific, not generic.
    tag = str(elem.tag).strip()
    if tag and norm(tag) not in {
        "item", "price", "product", "offer", "entry", "shopitem",
        "booster", "decal", "pack", "box"
    }:
        keys.append(tag)

    seen = set()
    out = []
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        try:
            hash31(key)
        except ValueError:
            continue
        out.append(key)
    return out


def is_excluded(elem: ET.Element, ancestry: list[ET.Element]) -> bool:
    # Cars are handled by CampaignCatalog, not CampaignStore.
    if any(norm(a.tag) == "car" for a in ancestry + [elem]):
        return True

    text = " ".join(
        [str(elem.tag)]
        + [f"{k}={v}" for k, v in elem.attrib.items()]
        + [str(a.tag) for a in ancestry[-3:]]
    ).lower()
    return any(h in norm(text) or h in text for h in REAL_MONEY_HINTS)


def direct_prices(elem: ET.Element) -> list[ET.Element]:
    return [c for c in list(elem) if norm(c.tag) == "price"]


def parse_price(p: ET.Element):
    currency = norm(p.get("Currency", p.get("currency", "")))
    if currency not in LOCAL_CURRENCY:
        return None
    try:
        price = int(float(p.get("Price", p.get("price", "0")) or 0))
    except ValueError:
        return None
    if price <= 0:
        return None
    return LOCAL_CURRENCY[currency], price


def walk(elem: ET.Element, ancestry: list[ET.Element], multiplier: float, rows, audit):
    prices = direct_prices(elem)
    if prices and not is_excluded(elem, ancestry):
        parsed = [x for x in (parse_price(p) for p in prices) if x]
        if parsed:
            # Campaign policy: prefer credits where available; otherwise
            # gameplay-earned premium. This deliberately removes dual-currency
            # monetization choice from the business layer.
            parsed.sort(key=lambda x: 0 if x[0] == "credits" else 1)
            currency, original = parsed[0]
            keys = element_keys(elem, prices)

            if keys:
                canonical = keys[0]
                item_id = hash31("item:" + canonical)
                quantity = get_quantity(elem)
                campaign_price = max(1, int(round(original * multiplier)))

                for key in keys:
                    row = {
                        "offer_key": key,
                        "item_id": item_id,
                        "quantity": quantity,
                        "currency": currency,
                        "price": campaign_price,
                        "unlock_node_id": 0,
                        "flags": 0,
                    }
                    rows.append(row)

                audit.append({
                    "tag": elem.tag,
                    "attributes": dict(elem.attrib),
                    "offer_keys": keys,
                    "canonical_key": canonical,
                    "item_id": item_id,
                    "quantity": quantity,
                    "original_currency": currency,
                    "original_price": original,
                    "campaign_price": campaign_price,
                })
            else:
                audit.append({
                    "tag": elem.tag,
                    "attributes": dict(elem.attrib),
                    "status": "skipped_no_stable_offer_key",
                    "prices": [
                        {"currency": c, "price": p} for c, p in parsed
                    ],
                })

    for child in list(elem):
        walk(child, ancestry + [elem], multiplier, rows, audit)


def build_rows(shop_xml: bytes, multiplier: float):
    text = shop_xml.decode("utf-8-sig", errors="replace")
    root = ET.fromstring(first_xml_document(text, "AsphaltShopConfiguration"))

    rows = []
    audit = []
    walk(root, [], multiplier, rows, audit)

    # offer_key hash is the runtime primary key. Reject aliases that collide
    # across different Campaign item identities.
    by_offer = {}
    collisions = []
    unique_rows = []
    for row in rows:
        offer_id = hash31(row["offer_key"])
        previous = by_offer.get(offer_id)
        identity = (
            row["item_id"], row["quantity"], row["currency"],
            row["price"], row["unlock_node_id"]
        )
        if previous:
            prev_identity = (
                previous["item_id"], previous["quantity"], previous["currency"],
                previous["price"], previous["unlock_node_id"]
            )
            if prev_identity != identity:
                collisions.append({
                    "offer_id": offer_id,
                    "first": previous,
                    "second": row,
                })
            continue
        by_offer[offer_id] = row
        unique_rows.append(row)

    return unique_rows, audit, collisions


def main() -> int:
    ap = argparse.ArgumentParser(description="Build local CampaignStore.dat from real asphaltshop.xtea")
    ap.add_argument("--xml-bin", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--multiplier", type=float, default=0.20)
    ns = ap.parse_args()

    if not 0 < ns.multiplier <= 1:
        raise SystemExit("multiplier must be >0 and <=1")

    shop = decode_shop(ns.xml_bin.resolve())
    rows, audit, collisions = build_rows(shop, ns.multiplier)

    report = {
        "source": str(ns.xml_bin.resolve()),
        "multiplier": ns.multiplier,
        "offer_alias_count": len(rows),
        "audited_purchase_groups": len(audit),
        "collision_count": len(collisions),
        "collisions": collisions,
        "audit": audit,
        "offers": rows,
        "policy": {
            "cars": "excluded; CampaignCatalog is authoritative",
            "real_money_iap": "excluded",
            "currency_choice": "credits preferred; otherwise gameplay-earned premium",
            "price": "20% of original positive local-currency price",
            "quantity": "explicit source quantity when present, otherwise one purchase unit",
        },
    }
    ns.report.parent.mkdir(parents=True, exist_ok=True)
    ns.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if collisions:
        ns.output.unlink(missing_ok=True)
        print(json.dumps({
            "status": "collision",
            "collision_count": len(collisions),
            "report": str(ns.report),
        }, indent=2))
        return 3

    if not rows:
        ns.output.unlink(missing_ok=True)
        print(json.dumps({
            "status": "no_verified_local_offers",
            "report": str(ns.report),
        }, indent=2))
        return 4

    data = store_binary.encode(rows)
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_bytes(data)

    print(json.dumps({
        "status": "ok",
        "offer_alias_count": len(rows),
        "output": str(ns.output),
        "report": str(ns.report),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
