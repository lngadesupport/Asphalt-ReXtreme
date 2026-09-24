#!/usr/bin/env python3
"""Create a disabled review template from a Replay/Photo hook audit candidate.

The output is NEVER verified/enabled. It reduces transcription mistakes by
copying candidate VA/file offset/instruction bytes and locating a potential CC
code cave. A human/runtime verification step is still mandatory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from campaign_msvc_rtti_map import PE32


class ProposalError(RuntimeError):
    pass


def parse_int(value: str) -> int:
    return int(value, 0)


def collect_site_bytes(candidate: dict, minimum: int = 5, maximum: int = 24) -> tuple[bytes, int]:
    data = bytearray()
    for ins in candidate.get("instructions", []):
        raw = bytes.fromhex(ins["bytes"])
        text = str(ins.get("text", "")).lower()
        mnemonic = text.split(" ", 1)[0]
        if mnemonic == "call" or mnemonic.startswith("j") or mnemonic.startswith("loop"):
            if len(data) < minimum:
                raise ProposalError("candidate begins with control flow before five relocatable bytes")
            break
        data += raw
        if len(data) >= minimum:
            break
        if len(data) > maximum:
            break
    if len(data) < minimum:
        raise ProposalError("candidate does not expose five safe whole-instruction bytes")
    site_va = int(candidate["method_va"], 16)
    return bytes(data), site_va + len(data)


def find_cc_cave(pe: PE32, minimum: int, avoid_off: int, avoid_len: int) -> tuple[int, int, int]:
    data = pe.data
    best = None
    i = 0
    while i < len(data):
        if data[i] != 0xCC:
            i += 1
            continue
        j = i + 1
        while j < len(data) and data[j] == 0xCC:
            j += 1
        length = j - i
        if length >= minimum and not (i < avoid_off + avoid_len and j > avoid_off):
            va = pe.off_to_va(i)
            if va is not None and pe.is_executable_va(va):
                best = (i, va, length)
                break
        i = j
    if best is None:
        raise ProposalError(f"no executable CC cave of at least {minimum} bytes found")
    return best


def select_candidate(audit: dict, method_va: int) -> dict:
    target = f"0x{method_va:08X}".lower()
    for row in audit.get("top_candidates", []):
        if str(row.get("method_va", "")).lower() == target:
            return row
    raise ProposalError(f"method VA 0x{method_va:08X} is not present in audit top_candidates")


def build_proposal(
    audit_path: Path,
    ams_path: Path,
    method_va: int,
    kind: str,
    cave_length: int,
) -> dict:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    candidate = select_candidate(audit, method_va)
    pe = PE32(ams_path)

    expected, resume_va = collect_site_bytes(candidate)
    site_off = pe.va_to_off(method_va)
    if site_off is None:
        raise ProposalError("candidate method VA is not file-backed")

    cave_off, cave_va, cave_run = find_cc_cave(pe, cave_length, site_off, len(expected))
    if kind == "replay":
        fmt = "rextreme-replay-frame-binding"
    elif kind == "photo":
        fmt = "rextreme-photo-frame-binding"
    else:
        fmt = "rextreme-photo-toggle-binding"

    return {
        "format": fmt,
        "version": 1,
        "build": "1.7.3.8-x86",
        "enabled": False,
        "rule": "AUTO-GENERATED REVIEW TEMPLATE. Do not enable until runtime verification proves this exact hook and register contract.",
        "binding": {
            "verified": False,
            "site_va": f"0x{method_va:08X}",
            "site_file_offset": f"0x{site_off:08X}",
            "expected_hex": expected.hex(" ").upper(),
            "resume_va": f"0x{resume_va:08X}",
            "cave_va": f"0x{cave_va:08X}",
            "cave_file_offset": f"0x{cave_off:08X}",
            "cave_length": cave_length,
            "cave_expected_hex": "CC",
            "this_register": "ecx",
            "evidence": [
                {
                    "audit": str(audit_path),
                    "class": candidate.get("class"),
                    "vtable_va": candidate.get("vtable_va"),
                    "slot_index": candidate.get("slot_index"),
                    "slot_offset": candidate.get("slot_offset"),
                    "method_va": candidate.get("method_va"),
                    "score": candidate.get("score"),
                    "reasons": candidate.get("reasons", []),
                    "cc_cave_run_length": cave_run,
                    "status": "candidate-only"
                }
            ]
        }
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate disabled hook-binding review template from audit")
    ap.add_argument("audit", type=Path)
    ap.add_argument("ams", type=Path)
    ap.add_argument("--method-va", required=True, type=parse_int)
    ap.add_argument("--kind", required=True, choices=["replay", "photo", "photo-toggle"])
    ap.add_argument("--cave-length", type=int, default=64)
    ap.add_argument("--out", required=True, type=Path)
    ns = ap.parse_args()

    try:
        proposal = build_proposal(
            ns.audit.resolve(),
            ns.ams.resolve(),
            ns.method_va,
            ns.kind,
            ns.cave_length,
        )
    except (OSError, json.JSONDecodeError, ValueError, ProposalError) as exc:
        print(f"ERROR: {exc}")
        return 1

    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] disabled review template: {ns.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
