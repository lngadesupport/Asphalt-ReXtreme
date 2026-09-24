#!/usr/bin/env python3
"""Audit candidate original Race HUD fields near verified GameModeGUIBase code.

Discovery-only. The tool finds instance-relative memory accesses and clusters
that may represent X/Y, scale, opacity or visibility of existing Asphalt
Xtreme HUD elements. It never emits verified bindings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from audit_replay_transform_bindings import (
    AuditError,
    Section,
    disassemble_accesses,
    frame_audit_sites,
    normalize_ranges,
    parse_pe,
)


@dataclass
class HudFieldCandidate:
    base_register: str
    displacement: int
    read_count: int
    write_count: int
    float_access_count: int
    byte_access_count: int
    instruction_count: int
    first_va: int
    last_va: int
    score: int
    status: str = "candidate-only"


def is_float_instruction(mnemonic: str) -> bool:
    m = mnemonic.lower()
    return (
        m.startswith("movss")
        or m.startswith("movsd")
        or m.startswith("addss")
        or m.startswith("subss")
        or m.startswith("mulss")
        or m.startswith("divss")
        or m.startswith("comiss")
        or m.startswith("ucomiss")
        or m.startswith("fld")
        or m.startswith("fst")
    )


def rank_fields(accesses) -> list[HudFieldCandidate]:
    buckets: dict[tuple[str, int], dict] = {}
    for row in accesses:
        if row.base in {"esp", "ebp", ""}:
            continue
        key = (row.base, row.displacement)
        b = buckets.setdefault(key, {
            "rows": [],
            "read": 0,
            "write": 0,
            "float": 0,
            "byte": 0,
        })
        b["rows"].append(row)
        if row.access == "read":
            b["read"] += 1
        elif row.access == "write":
            b["write"] += 1
        if is_float_instruction(row.mnemonic):
            b["float"] += 1
        # Capstone operand byte width is not exposed in our compact MemoryAccess;
        # common byte mov/set instructions are still useful weak evidence.
        if row.mnemonic.lower() in {"setne", "sete", "setnz", "setz", "movzx"}:
            b["byte"] += 1

    out: list[HudFieldCandidate] = []
    for (base, displacement), b in buckets.items():
        rows = sorted(b["rows"], key=lambda x: x.va)
        score = min(len(rows), 12) * 3
        score += min(b["write"], 8) * 6
        score += min(b["float"], 8) * 5
        score += min(b["byte"], 4) * 3
        # HUD state is often read and written by the same object/update path.
        if b["read"] and b["write"]:
            score += 12
        out.append(HudFieldCandidate(
            base_register=base,
            displacement=displacement,
            read_count=b["read"],
            write_count=b["write"],
            float_access_count=b["float"],
            byte_access_count=b["byte"],
            instruction_count=len(rows),
            first_va=rows[0].va,
            last_va=rows[-1].va,
            score=score,
        ))

    out.sort(key=lambda x: (-x.score, x.base_register, x.displacement))
    return out


def neighbor_groups(fields: list[HudFieldCandidate]) -> list[dict]:
    """Group adjacent offsets on the same object; useful for XY/scale/opacity."""
    by_base: dict[str, list[HudFieldCandidate]] = {}
    for field in fields:
        by_base.setdefault(field.base_register, []).append(field)

    groups: list[dict] = []
    for base, items in by_base.items():
        items = sorted(items, key=lambda x: x.displacement)
        for i, first in enumerate(items):
            group = [first]
            last = first.displacement
            for nxt in items[i + 1:]:
                delta = nxt.displacement - last
                if delta in (1, 2, 4):
                    group.append(nxt)
                    last = nxt.displacement
                    if len(group) >= 5:
                        break
                elif nxt.displacement - first.displacement > 0x20:
                    break
            if len(group) >= 2:
                groups.append({
                    "base_register": base,
                    "offsets": [f"{x.displacement:+#x}" for x in group],
                    "scores": [x.score for x in group],
                    "shape": (
                        "adjacent-float-style"
                        if all(x.float_access_count for x in group[:2])
                        else "adjacent-fields"
                    ),
                    "status": "candidate-only",
                })

    unique: dict[tuple, dict] = {}
    for g in groups:
        key = (g["base_register"], tuple(g["offsets"]))
        unique[key] = g
    return sorted(unique.values(), key=lambda g: (-sum(g["scores"]), g["base_register"]))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit candidate fields of original Asphalt Xtreme Race HUD objects"
    )
    ap.add_argument("ams", type=Path)
    ap.add_argument("--start-va", action="append", type=lambda x: int(x, 0), default=[])
    ap.add_argument("--frame-audit", type=Path)
    ap.add_argument("--length", type=lambda x: int(x, 0), default=0x1000)
    ap.add_argument("--out", type=Path, default=Path("race-hud-field-audit.json"))
    ns = ap.parse_args()

    try:
        path = ns.ams.resolve()
        data = path.read_bytes()
        image_base, timestamp, size_of_image, sections = parse_pe(data)

        starts = list(ns.start_va)
        starts.extend(frame_audit_sites(ns.frame_audit))
        if not starts:
            raise AuditError(
                "no code range supplied; pass --start-va or --frame-audit from a verified GUI hook audit"
            )

        ranges = normalize_ranges(starts, ns.length, image_base, size_of_image)
        accesses = []
        range_info = []
        for start, length in ranges:
            rows = disassemble_accesses(data, image_base, sections, start, length)
            accesses.extend(rows)
            range_info.append({
                "start_va": f"0x{start:08X}",
                "length": length,
                "memory_access_count": len(rows),
            })

        fields = rank_fields(accesses)
        groups = neighbor_groups(fields)

        report = {
            "format": "rextreme-race-hud-field-audit",
            "version": 1,
            "rule": (
                "Every result is candidate-only. Promote a HUD property only after "
                "runtime verification that the target belongs to an existing original "
                "Asphalt Xtreme HUD element and that changing it has exactly the expected effect."
            ),
            "binary": str(path),
            "sha256": hashlib.sha256(data).hexdigest(),
            "pe": {
                "image_base": f"0x{image_base:08X}",
                "time_date_stamp": f"0x{timestamp:08X}",
                "size_of_image": f"0x{size_of_image:08X}",
            },
            "ranges": range_info,
            "summary": {
                "memory_accesses": len(accesses),
                "candidate_fields": len(fields),
                "neighbor_groups": len(groups),
            },
            "candidate_fields": [
                {
                    **asdict(x),
                    "displacement": f"{x.displacement:+#x}",
                    "first_va": f"0x{x.first_va:08X}",
                    "last_va": f"0x{x.last_va:08X}",
                }
                for x in fields
            ],
            "neighbor_groups": groups,
            "verified_bindings": [],
        }

        ns.out.parent.mkdir(parents=True, exist_ok=True)
        ns.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] wrote {ns.out}")
        print(json.dumps(report["summary"], indent=2))
        return 0
    except (OSError, ValueError, AuditError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
