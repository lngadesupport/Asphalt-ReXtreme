#!/usr/bin/env python3
"""Find evidence-backed candidates for Replay frame sampling and presentation hooks.

This is a discovery tool, not a patcher. It anchors itself to already-verified
Asphalt Xtreme 1.7.3.8 sites and MSVC RTTI, then enumerates candidate virtual
methods for GameModeGUIBase / related presentation classes.

Nothing produced here is marked VERIFIED automatically.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from campaign_msvc_rtti_map import PE32, map_class

BEGIN_SITE_VA = 0x00C7E73B
BEGIN_SITE_OFF = 0x0087DB3B
BEGIN_SITE_ORIG = bytes.fromhex("8B C3 8B 4D F4")
FINISH_SITE_VA = 0x00CC8828
FINISH_SITE_OFF = 0x008C7C28
FINISH_SITE_ORIG = bytes.fromhex("8B 75 EC C7 45 FC FF FF FF FF")

KEYWORDS = (
    "gamemode", "race", "camera", "pause", "hud", "gui", "render",
    "settings", "graphics", "replay", "photo", "vehicle", "car",
)

TYPE_RE = re.compile(rb"\.\?AV[^\x00]{1,180}@@\x00")
MEM_WRITE_RE = re.compile(
    r"^(?:mov|movss|movsd|fst|fstp|inc|dec|add|sub|and|or|xor)\s+"
    r"(?:byte ptr |word ptr |dword ptr |qword ptr )?"
    r"\[([a-z]{2,3})(?:\s*\+\s*(0x[0-9a-f]+|\d+))?\]",
    re.IGNORECASE,
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def undecorate_simple(name: str) -> str:
    if not name.startswith(".?AV") or not name.endswith("@@"):
        return name
    body = name[4:-2]
    parts = [p for p in body.split("@") if p]
    if not parts:
        return name
    if len(parts) == 1:
        return parts[0]
    return "::".join(reversed(parts[1:])) + "::" + parts[0]


def discover_keyword_classes(pe: PE32, max_classes: int = 256) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in TYPE_RE.finditer(pe.data):
        raw = m.group(0)[:-1]
        try:
            decorated = raw.decode("ascii")
        except UnicodeDecodeError:
            continue
        low = decorated.lower()
        if not any(k in low for k in KEYWORDS):
            continue
        name = undecorate_simple(decorated)
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= max_classes:
            break
    return out


def xrefs_to_va(pe: PE32, va: int, executable_only: bool = True, limit: int = 64) -> list[int]:
    needle = struct.pack("<I", va & 0xFFFFFFFF)
    hits: list[int] = []
    for off in pe.find_all(needle):
        ref_va = pe.off_to_va(off)
        if ref_va is None:
            continue
        if executable_only and not pe.is_executable_va(ref_va):
            continue
        hits.append(ref_va)
        if len(hits) >= limit:
            break
    return hits


def get_capstone():
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "capstone is required: py -3 -m pip install capstone"
        ) from exc
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = False
    return md


def function_bytes(pe: PE32, va: int, max_bytes: int = 512) -> bytes:
    off = pe.va_to_off(va)
    if off is None:
        return b""
    return pe.data[off:off + max_bytes]


def disassemble_method(pe: PE32, va: int, max_instructions: int = 96) -> dict:
    md = get_capstone()
    blob = function_bytes(pe, va)
    instructions: list[dict] = []
    calls: list[str] = []
    refs_game_mode_field = 0
    refs_float = 0
    branches = 0
    ret_seen = False

    for ins in md.disasm(blob, va):
        text = f"{ins.mnemonic} {ins.op_str}".strip()
        instructions.append({
            "va": f"0x{ins.address:08X}",
            "bytes": ins.bytes.hex(" ").upper(),
            "text": text,
        })

        low = text.lower()
        if ins.mnemonic == "call":
            calls.append(ins.op_str)
        if ins.mnemonic.startswith("j"):
            branches += 1
        if "+ 0x14" in low or "+0x14" in low:
            refs_game_mode_field += 1
        if ins.mnemonic.startswith(("movss", "addss", "subss", "mulss", "divss")):
            refs_float += 1
        if ins.mnemonic.startswith("ret"):
            ret_seen = True
            break
        if len(instructions) >= max_instructions:
            break

    field_writes = extract_field_writes(instructions)
    return {
        "instructions": instructions,
        "instruction_count": len(instructions),
        "call_count": len(calls),
        "calls": calls[:24],
        "branch_count": branches,
        "refs_game_mode_field_0x14": refs_game_mode_field,
        "scalar_float_ops": refs_float,
        "field_writes": field_writes,
        "field_write_count": len(field_writes),
        "ret_seen": ret_seen,
    }


def extract_field_writes(instructions: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for ins in instructions:
        text = str(ins.get("text", ""))
        m = MEM_WRITE_RE.match(text)
        if not m:
            continue
        reg = m.group(1).lower()
        raw_disp = m.group(2)
        displacement = int(raw_disp, 0) if raw_disp else 0
        mnemonic = text.split(" ", 1)[0].lower()
        rows.append({
            "va": ins.get("va"),
            "text": text,
            "base_register": reg,
            "field_offset": displacement,
            "field_offset_hex": f"0x{displacement:X}",
            "scalar_float_write": mnemonic in {"movss", "movsd", "fst", "fstp"},
            "status": "candidate-only",
        })
    return rows


def score_method(method: dict, slot: int, xrefs: list[int]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    n = method["instruction_count"]
    calls = method["call_count"]

    if 12 <= n <= 96:
        score += 2
        reasons.append("non-trivial method size")
    if calls >= 1:
        score += 2
        reasons.append("contains calls")
    if calls >= 3:
        score += 1
        reasons.append("update-like call density")
    if method["branch_count"] >= 2:
        score += 1
        reasons.append("state/control branches")
    if method["refs_game_mode_field_0x14"] > 0:
        score += 4
        reasons.append("references GameModeGUIBase+0x14")
    if method["scalar_float_ops"] > 0:
        score += 2
        reasons.append("scalar float operations")
    if method.get("field_write_count", 0) > 0:
        score += 2
        reasons.append("writes object fields")
    if any(row.get("scalar_float_write") for row in method.get("field_writes", [])):
        score += 2
        reasons.append("writes scalar float field")
    if method["ret_seen"]:
        score += 1
    if xrefs:
        score += 1
        reasons.append("direct executable xref")
    if slot in (0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x30):
        score += 1
        reasons.append("early virtual slot")

    return score, reasons


def analyze_vtable(pe: PE32, class_name: str, item: dict, max_methods: int) -> dict:
    methods_out: list[dict] = []
    for index, va_text in enumerate(item.get("methods", [])[:max_methods]):
        va = int(va_text, 16)
        off = pe.va_to_off(va)
        method = disassemble_method(pe, va)
        xrefs = xrefs_to_va(pe, va)
        slot = index * 4
        score, reasons = score_method(method, slot, xrefs)
        methods_out.append({
            "class": class_name,
            "vtable_va": item["vtable_va"],
            "slot_index": index,
            "slot_offset": f"0x{slot:02X}",
            "method_va": va_text,
            "method_file_offset": None if off is None else f"0x{off:08X}",
            "score": score,
            "reasons": reasons,
            "direct_xrefs": [f"0x{x:08X}" for x in xrefs],
            **method,
            "status": "candidate-only",
        })
    methods_out.sort(key=lambda x: (-x["score"], x["slot_index"]))
    return {
        "class": class_name,
        "vtable_va": item["vtable_va"],
        "object_offset": item.get("object_offset"),
        "methods": methods_out,
    }


def verify_anchor(data: bytes, off: int, expected: bytes, label: str) -> dict:
    got = data[off:off + len(expected)]
    return {
        "label": label,
        "file_offset": f"0x{off:08X}",
        "matches": got == expected,
        "expected": expected.hex(" ").upper(),
        "actual": got.hex(" ").upper(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit candidate per-frame/camera/pause hooks in Asphalt Xtreme 1.7.3.8"
    )
    ap.add_argument("ams", type=Path)
    ap.add_argument("--out", type=Path, default=Path("replay-frame-hook-audit.json"))
    ap.add_argument("--max-methods", type=int, default=64)
    ap.add_argument("--max-classes", type=int, default=160)
    ns = ap.parse_args()

    ams = ns.ams.resolve()
    if not ams.is_file():
        ap.error(f"AMS.exe not found: {ams}")

    pe = PE32(ams)
    anchors = [
        verify_anchor(pe.data, BEGIN_SITE_OFF, BEGIN_SITE_ORIG, "verified GameModeGUIBase begin site"),
        verify_anchor(pe.data, FINISH_SITE_OFF, FINISH_SITE_ORIG, "verified result-screen finish site"),
    ]

    classes = discover_keyword_classes(pe, ns.max_classes)
    priority = [
        "GameModeGUIBase",
        "GameModeBase",
        "Camera",
        "CameraManager",
        "PauseMenu",
        "HUD",
    ]
    for name in reversed(priority):
        if name in classes:
            classes.remove(name)
        classes.insert(0, name)

    mapped: list[dict] = []
    candidate_methods: list[dict] = []
    seen_vtables: set[str] = set()

    for class_name in classes:
        result = map_class(pe, class_name, ns.max_methods)
        matches = result.get("matches", [])
        if not matches:
            continue
        class_entry = {
            "requested": class_name,
            "decorated_name": result.get("decorated_name"),
            "vtables": [],
        }
        for item in matches:
            vtable = item["vtable_va"]
            if vtable in seen_vtables:
                continue
            seen_vtables.add(vtable)
            analyzed = analyze_vtable(pe, class_name, item, ns.max_methods)
            class_entry["vtables"].append(analyzed)
            candidate_methods.extend(analyzed["methods"])
        if class_entry["vtables"]:
            mapped.append(class_entry)

    candidate_methods.sort(key=lambda x: (-x["score"], x["class"], x["slot_index"]))

    report = {
        "format": "rextreme-replay-frame-hook-audit",
        "version": 1,
        "binary": str(ams),
        "sha256": sha256(ams),
        "image_base": f"0x{pe.image_base:08X}",
        "known_verified_anchors": anchors,
        "rule": (
            "All method rows are candidate-only. A per-frame, camera, pause or HUD binding "
            "must be manually verified against runtime behavior before it may enter the "
            "ReXtreme verified binding registry."
        ),
        "keyword_classes_discovered": classes,
        "mapped_classes": mapped,
        "top_candidates": candidate_methods[:120],
        "top_field_write_candidates": [
            {
                "class": row["class"],
                "vtable_va": row["vtable_va"],
                "slot_index": row["slot_index"],
                "slot_offset": row["slot_offset"],
                "method_va": row["method_va"],
                "score": row["score"],
                "field_writes": row.get("field_writes", []),
                "status": "candidate-only",
            }
            for row in candidate_methods
            if row.get("field_write_count", 0) > 0
        ][:120],
        "verified_bindings": [],
    }

    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] wrote {ns.out}")
    print(f"[ANCHORS] {sum(1 for x in anchors if x['matches'])}/{len(anchors)} verified bytes matched")
    print(f"[RTTI] {len(mapped)} keyword classes mapped")
    print(f"[METHODS] {len(candidate_methods)} candidate virtual methods")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
