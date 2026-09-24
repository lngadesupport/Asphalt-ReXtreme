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

from xtea_assets import decode_stream, DecodeError
import build_campaign_objective_catalog as objective_binary
import build_campaign_upgrade_ui_map as ui_binary
from build_campaign_objective_catalog_from_package import convert as convert_objectives

PART = {
    "topspeed": 0,
    "top_speed": 0,
    "top speed": 0,
    "speed": 0,
    "acceleration": 1,
    "accel": 1,
    "handling": 2,
    "handle": 2,
    "nitro": 3,
}

ID_KEYS = (
    "id", "item_id", "itemid", "card_id", "cardid",
    "upgrade_id", "upgradeid", "prokit_id", "prokitid",
    "tool_id", "toolid", "content_id", "contentid",
)
PART_KEYS = ("car_part", "carpart", "part", "part_name", "partname", "subtype")
KIND_KEYS = ("kind", "type", "category", "group", "family")


def norm(v: object) -> str:
    s = str(v).strip()
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s)
    return s.strip("_").lower()


def part_value(v: object) -> int | None:
    raw = str(v).strip().lower()
    compact = norm(v)
    if raw in PART:
        return PART[raw]
    if compact in PART:
        return PART[compact]
    return None


def int_value(v: object) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v if v > 0 else None
    if isinstance(v, float) and v.is_integer() and v > 0:
        return int(v)
    s = str(v).strip()
    if re.fullmatch(r"[1-9][0-9]*", s):
        return int(s)
    return None


def infer_kind(record: dict, source_name: str) -> str | None:
    tokens = [source_name]
    for k in KIND_KEYS:
        for rk, rv in record.items():
            if norm(rk) == k:
                tokens.append(str(rv))
    joined = " ".join(tokens).lower()

    if "prokit" in joined or "pro_kit" in joined or "tuning" in joined:
        return "prokit"
    if "upgrade" in joined or "card" in joined or "tool" in joined:
        return "upgrade"
    return None


def candidate_from_record(record: dict, source: str, path: str):
    normalized = {norm(k): v for k, v in record.items()}

    part_key = next((k for k in PART_KEYS if k in normalized and part_value(normalized[k]) is not None), None)
    if not part_key:
        return None

    part = part_value(normalized[part_key])
    ids = []
    for key in ID_KEYS:
        if key in normalized:
            val = int_value(normalized[key])
            if val:
                ids.append((key, val))

    ids = list(dict.fromkeys(ids))
    if len(ids) != 1:
        return {
            "unresolved": True,
            "source": source,
            "path": path,
            "reason": "car_part record has zero or multiple numeric content ids",
            "part": part,
            "ids": ids,
            "record": record,
        }

    kind = infer_kind(record, source + " " + path)
    if not kind:
        return {
            "unresolved": True,
            "source": source,
            "path": path,
            "reason": "content id + car_part found but upgrade/prokit kind is ambiguous",
            "part": part,
            "ids": ids,
            "record": record,
        }

    return {
        "unresolved": False,
        "source": source,
        "path": path,
        "ui_action_id": ids[0][1],
        "kind": kind,
        "part_slot": part,
        "flags": 0,
    }


def walk_json(value, source: str, path: str = "$"):
    if isinstance(value, dict):
        cand = candidate_from_record(value, source, path)
        if cand:
            yield cand
        for k, v in value.items():
            yield from walk_json(v, source, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk_json(v, source, f"{path}[{i}]")


def xml_record(elem: ET.Element) -> dict:
    rec = dict(elem.attrib)
    for child in list(elem):
        if len(child) == 0 and child.text and child.text.strip():
            rec.setdefault(child.tag, child.text.strip())
    return rec


def walk_xml(elem: ET.Element, source: str, path: str = ""):
    here = f"{path}/{elem.tag}" if path else f"/{elem.tag}"
    rec = xml_record(elem)
    cand = candidate_from_record(rec, source, here)
    if cand:
        yield cand
    for child in list(elem):
        yield from walk_xml(child, source, here)


def decode_entries(xml_bin: Path):
    with zipfile.ZipFile(xml_bin, "r") as z:
        for info in z.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".xtea"):
                continue
            try:
                payload, meta = decode_stream(z.read(info.filename))
            except DecodeError:
                continue
            yield info.filename, payload, meta


def parse_payload(name: str, payload: bytes):
    stripped = payload.lstrip(b"\xef\xbb\xbf\x00\x20\r\n\t")
    if not stripped:
        return None, None
    try:
        if stripped[:1] in (b"{", b"["):
            return "json", json.loads(payload.decode("utf-8-sig").rstrip("\x00 "))
        if stripped[:1] == b"<":
            text = payload.decode("utf-8-sig", errors="strict").rstrip("\x00 ")
            return "xml", ET.fromstring(text)
    except (UnicodeError, json.JSONDecodeError, ET.ParseError):
        return None, None
    return None, None


def build_objectives(career: dict, output: Path, report: Path):
    rows, unresolved = convert_objectives(career)
    payload = {
        "recognized_objectives": len(rows),
        "unresolved_count": len(unresolved),
        "unresolved": unresolved,
        "objectives": rows,
    }
    report.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if unresolved:
        return False, payload

    entries = objective_binary.normalize(rows)
    output.write_bytes(objective_binary.build(entries))
    return True, payload


def build_ui_map(candidates, output: Path, report: Path):
    resolved = {}
    conflicts = []
    unresolved = [x for x in candidates if x.get("unresolved")]

    for row in candidates:
        if row.get("unresolved"):
            continue
        ui_id = int(row["ui_action_id"])
        value = (row["kind"], int(row["part_slot"]))
        previous = resolved.get(ui_id)
        if previous and previous[:2] != value:
            conflicts.append({
                "ui_action_id": ui_id,
                "previous": previous,
                "new": row,
            })
            continue
        resolved[ui_id] = (
            row["kind"],
            int(row["part_slot"]),
            row["source"],
            row["path"],
        )

    rows = [
        {
            "ui_action_id": ui_id,
            "kind": value[0],
            "part_slot": value[1],
            "flags": 0,
        }
        for ui_id, value in sorted(resolved.items())
    ]

    payload = {
        "verified_client_enum": {
            "0": "top_speed",
            "1": "acceleration",
            "2": "handling",
            "3": "nitro",
        },
        "mapped_count": len(rows),
        "conflict_count": len(conflicts),
        "unresolved_car_part_records": unresolved,
        "conflicts": conflicts,
        "entries": rows,
        "sources": [
            {
                "ui_action_id": ui_id,
                "source": value[2],
                "path": value[3],
            }
            for ui_id, value in sorted(resolved.items())
        ],
    }
    report.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if conflicts or not rows:
        return False, payload

    entries = ui_binary.normalize(rows)
    output.write_bytes(ui_binary.build(entries))
    return True, payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Build strict Campaign auxiliary catalogs from xml.bin")
    ap.add_argument("--xml-bin", type=Path, required=True)
    ap.add_argument("--package-dir", type=Path, required=True)
    ap.add_argument("--report-dir", type=Path, required=True)
    ns = ap.parse_args()

    xml_bin = ns.xml_bin.resolve()
    package = ns.package_dir.resolve()
    reports = ns.report_dir.resolve()
    package.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    career = None
    candidates = []
    decoded = []

    for name, payload, meta in decode_entries(xml_bin):
        decoded.append({"name": name, **meta})
        if Path(name).name.lower() == "career_data.xtea":
            try:
                career = json.loads(payload.decode("utf-8-sig").rstrip("\x00 "))
            except Exception as exc:
                raise SystemExit(f"career_data decode failed: {exc}")

        typ, parsed = parse_payload(name, payload)
        if typ == "json":
            candidates.extend(walk_json(parsed, name))
        elif typ == "xml":
            candidates.extend(walk_xml(parsed, name))

    if career is None:
        raise SystemExit("career_data.xtea not found in xml.bin")

    obj_ok, obj_report = build_objectives(
        career,
        package / "CampaignObjectives.dat",
        reports / "CampaignObjectives.report.json",
    )
    ui_ok, ui_report = build_ui_map(
        candidates,
        package / "CampaignUpgradeUiMap.dat",
        reports / "CampaignUpgradeUiMap.report.json",
    )

    status = {
        "xml_bin": str(xml_bin),
        "decoded_entries": len(decoded),
        "objectives_ready": obj_ok,
        "objectives_count": obj_report["recognized_objectives"],
        "objective_unresolved_count": obj_report["unresolved_count"],
        "upgrade_ui_map_ready": ui_ok,
        "upgrade_ui_map_count": ui_report["mapped_count"],
        "upgrade_ui_conflict_count": ui_report["conflict_count"],
        "reports": str(reports),
    }
    (reports / "CampaignAuxiliary.status.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(status, indent=2, ensure_ascii=False))

    # Objectives are required for career authority. UI-map absence only blocks
    # the upgrade adapter; all other rebuilt systems remain buildable.
    if not obj_ok:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
