#!/usr/bin/env python3
"""Audit MSVC RTTI/vtables related to the original Asphalt Xtreme UI.

Discovery only: no class/vtable/reference is automatically considered a safe
ReXtreme binding. The output exists to accelerate manual verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from campaign_msvc_rtti_map import PE32, map_class

TERMS = (
    "gui", "ui", "menu", "setting", "option", "pause", "hud", "screen",
    "button", "slider", "toggle", "checkbox", "panel", "popup", "dialog",
    "list", "tab", "label", "widget", "layout", "view",
)

RTTI_RE = re.compile(rb"\.\?A[VU][A-Za-z0-9_@$?]+@@\x00")


def class_score(name: str) -> tuple[int, list[str]]:
    low = name.lower()
    hits = [term for term in TERMS if term in low]
    score = len(hits) * 20
    if "gui" in hits or "ui" in hits:
        score += 15
    if "menu" in hits or "screen" in hits:
        score += 10
    return score, hits


def executable_vtable_refs(pe: PE32, vtable_va: int, limit: int = 64) -> list[dict]:
    refs: list[dict] = []
    needle = struct.pack("<I", vtable_va)
    for off in pe.find_all(needle):
        va = pe.off_to_va(off)
        if va is None or not pe.is_executable_va(va):
            continue
        refs.append({
            "file_offset": off,
            "va": va,
            "rva": va - pe.image_base,
            "status": "candidate-only",
        })
        if len(refs) >= limit:
            break
    return refs


def enumerate_candidates(pe: PE32, max_methods: int) -> list[dict]:
    decorated = sorted({
        m.group(0)[:-1].decode("ascii", errors="ignore")
        for m in RTTI_RE.finditer(pe.data)
    })

    out: list[dict] = []
    for name in decorated:
        score, hits = class_score(name)
        if score <= 0:
            continue

        mapped = map_class(pe, name, max_methods)
        for match in mapped["matches"]:
            vtable_va = int(match["vtable_va"], 16)
            refs = executable_vtable_refs(pe, vtable_va)
            out.append({
                "score": score + min(len(refs), 12) * 5,
                "keyword_hits": hits,
                "decorated_name": name,
                "type_descriptor_va": match["type_descriptor_va"],
                "complete_object_locator_va": match["complete_object_locator_va"],
                "vtable_va": match["vtable_va"],
                "vtable_rva": f"0x{vtable_va - pe.image_base:08X}",
                "methods": match["methods"],
                "executable_vtable_refs": [
                    {
                        **r,
                        "file_offset": f"0x{r['file_offset']:08X}",
                        "va": f"0x{r['va']:08X}",
                        "rva": f"0x{r['rva']:08X}",
                    }
                    for r in refs
                ],
                "status": "candidate-only",
                "verified": False,
            })

    out.sort(
        key=lambda x: (
            -x["score"],
            -len(x["executable_vtable_refs"]),
            x["decorated_name"],
            x["vtable_va"],
        )
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit original Asphalt Xtreme UI RTTI/vtables"
    )
    ap.add_argument("ams", type=Path)
    ap.add_argument("--out", type=Path, default=Path("original-ui-rtti-audit.json"))
    ap.add_argument("--max-methods", type=int, default=64)
    ns = ap.parse_args()

    if ns.max_methods < 1 or ns.max_methods > 256:
        ap.error("--max-methods must be 1..256")

    try:
        pe = PE32(ns.ams.resolve())
        candidates = enumerate_candidates(pe, ns.max_methods)
    except (OSError, ValueError, struct.error) as exc:
        print(f"ERROR: {exc}")
        return 1

    report = {
        "format": "rextreme-original-ui-rtti-audit",
        "version": 1,
        "rule": (
            "RTTI/vtable results are candidate-only. A binding requires exact class role, "
            "lifetime, method semantics, PE fingerprint and runtime behavior verification."
        ),
        "binary": str(ns.ams.resolve()),
        "sha256": hashlib.sha256(pe.data).hexdigest(),
        "pe": {
            "image_base": f"0x{pe.image_base:08X}",
            "time_date_stamp": f"0x{pe.time_date_stamp:08X}",
            "size_of_image": f"0x{pe.size_of_image:08X}",
        },
        "summary": {
            "candidate_classes": len(candidates),
            "classes_with_executable_vtable_refs": sum(
                1 for x in candidates if x["executable_vtable_refs"]
            ),
        },
        "candidates": candidates,
        "verified_bindings": [],
    }

    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] wrote {ns.out}")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
