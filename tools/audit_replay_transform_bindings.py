#!/usr/bin/env python3
"""Audit candidate Replay transform fields in Asphalt Xtreme 1.7.3.8 x86.

This tool is evidence-first. It disassembles caller-selected or seeded code
ranges and reports memory-access clusters that may correspond to transform,
quaternion, velocity, time or entity fields. Nothing is promoted to a verified
Replay binding automatically.

Typical use:
  py -3 tools/audit_replay_transform_bindings.py AMS.exe --out replay-transform-audit.json

Optional:
  --start-va 0x00E42100 --length 0x800
  --frame-audit _TRACE_MONTAR/replay-frame-audit.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

IMAGE_BASE = 0x00400000

# Existing verified race adapter seed from CampaignCore.c:
# CAMPAIGN_AMS_RVA_RESOLVE_CURRENT_RACE = 0x00A42100
DEFAULT_SEED_RVAS = (0x00A42100,)


class AuditError(RuntimeError):
    pass


@dataclass
class Section:
    name: str
    virtual_address: int
    virtual_size: int
    raw_offset: int
    raw_size: int
    characteristics: int


@dataclass
class MemoryAccess:
    va: int
    size: int
    mnemonic: str
    op_str: str
    base: str
    index: str | None
    scale: int
    displacement: int
    access: str
    instruction_bytes: str


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_pe(data: bytes) -> tuple[int, int, int, list[Section]]:
    if len(data) < 0x100 or data[:2] != b"MZ":
        raise AuditError("not an MZ executable")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 0x18 >= len(data) or data[pe:pe + 4] != b"PE\0\0":
        raise AuditError("invalid PE signature")
    machine = struct.unpack_from("<H", data, pe + 4)[0]
    if machine != 0x014C:
        raise AuditError(f"expected x86 PE, got machine 0x{machine:04X}")
    number_of_sections = struct.unpack_from("<H", data, pe + 6)[0]
    time_date_stamp = struct.unpack_from("<I", data, pe + 8)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    if opt + opt_size > len(data):
        raise AuditError("truncated optional header")
    if struct.unpack_from("<H", data, opt)[0] != 0x010B:
        raise AuditError("expected PE32")
    image_base = struct.unpack_from("<I", data, opt + 28)[0]
    size_of_image = struct.unpack_from("<I", data, opt + 56)[0]

    sections: list[Section] = []
    table = opt + opt_size
    for i in range(number_of_sections):
        off = table + i * 40
        if off + 40 > len(data):
            raise AuditError("truncated section table")
        raw_name = data[off:off + 8].split(b"\0", 1)[0]
        name = raw_name.decode("ascii", errors="replace")
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", data, off + 8
        )
        characteristics = struct.unpack_from("<I", data, off + 36)[0]
        sections.append(
            Section(
                name,
                virtual_address,
                virtual_size,
                raw_offset,
                raw_size,
                characteristics,
            )
        )
    return image_base, time_date_stamp, size_of_image, sections


def rva_to_raw(rva: int, sections: Iterable[Section]) -> int | None:
    for s in sections:
        span = max(s.virtual_size, s.raw_size)
        if s.virtual_address <= rva < s.virtual_address + span:
            delta = rva - s.virtual_address
            if delta >= s.raw_size:
                return None
            return s.raw_offset + delta
    return None


def va_to_raw(va: int, image_base: int, sections: Iterable[Section]) -> int | None:
    if va < image_base:
        return None
    return rva_to_raw(va - image_base, sections)


def parse_int(value: str) -> int:
    return int(value, 0)


def normalize_ranges(
    starts: list[int],
    length: int,
    image_base: int,
    size_of_image: int,
) -> list[tuple[int, int]]:
    if length <= 0 or length > 0x20000:
        raise AuditError("length must be 1..0x20000")
    out: list[tuple[int, int]] = []
    seen: set[int] = set()
    for value in starts:
        va = value if value >= image_base else image_base + value
        if va in seen:
            continue
        if va < image_base or va >= image_base + size_of_image:
            raise AuditError(f"range start outside image: 0x{va:08X}")
        seen.add(va)
        out.append((va, length))
    return out


def frame_audit_sites(path: Path | None) -> list[int]:
    if path is None:
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    sites: list[int] = []
    for key in ("candidates", "hooks", "evidence"):
        rows = data.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            for field in ("site_va", "va", "instruction_va", "hook_va"):
                value = row.get(field)
                if isinstance(value, int):
                    sites.append(value)
                    break
                if isinstance(value, str):
                    try:
                        sites.append(int(value, 0))
                        break
                    except ValueError:
                        pass
    return sites


def disassemble_accesses(
    data: bytes,
    image_base: int,
    sections: list[Section],
    start_va: int,
    length: int,
) -> list[MemoryAccess]:
    try:
        from capstone import (
            Cs,
            CS_ARCH_X86,
            CS_MODE_32,
            CS_AC_READ,
            CS_AC_WRITE,
        )
        from capstone.x86 import X86_OP_MEM
    except ImportError as exc:
        raise AuditError(
            "capstone is required: py -3 -m pip install capstone"
        ) from exc

    raw = va_to_raw(start_va, image_base, sections)
    if raw is None:
        raise AuditError(f"VA 0x{start_va:08X} is not backed by file data")

    max_len = min(length, len(data) - raw)
    blob = data[raw:raw + max_len]

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    rows: list[MemoryAccess] = []

    for ins in md.disasm(blob, start_va):
        for op in ins.operands:
            if op.type != X86_OP_MEM:
                continue
            mem = op.mem
            base = ins.reg_name(mem.base) if mem.base else ""
            index = ins.reg_name(mem.index) if mem.index else None
            if not base:
                continue

            access = "unknown"
            if op.access & CS_AC_WRITE:
                access = "write"
            elif op.access & CS_AC_READ:
                access = "read"

            rows.append(
                MemoryAccess(
                    va=ins.address,
                    size=ins.size,
                    mnemonic=ins.mnemonic,
                    op_str=ins.op_str,
                    base=base,
                    index=index,
                    scale=mem.scale,
                    displacement=mem.disp,
                    access=access,
                    instruction_bytes=bytes(ins.bytes).hex(" ").upper(),
                )
            )
    return rows


def cluster_accesses(
    accesses: list[MemoryAccess],
    max_instruction_distance: int = 0x50,
) -> list[dict]:
    """Find same-base +4-byte displacement clusters within a small code window."""
    clusters: list[dict] = []
    by_base: dict[str, list[MemoryAccess]] = {}

    for row in accesses:
        # ESP/EBP traffic is usually stack-local noise for this purpose.
        if row.base in {"esp", "ebp"}:
            continue
        by_base.setdefault(row.base, []).append(row)

    for base, rows in by_base.items():
        rows = sorted(rows, key=lambda r: (r.va, r.displacement))
        for i, first in enumerate(rows):
            group = [first]
            last_disp = first.displacement
            last_va = first.va
            for nxt in rows[i + 1:]:
                if nxt.va - first.va > max_instruction_distance:
                    break
                if nxt.displacement == last_disp + 4 and nxt.va >= last_va:
                    group.append(nxt)
                    last_disp = nxt.displacement
                    last_va = nxt.va
                elif nxt.displacement <= last_disp:
                    continue
            if len(group) < 3:
                continue

            kind = "vector3"
            if len(group) >= 4:
                kind = "quaternion-or-vector4"

            signature = (
                base,
                group[0].va,
                tuple(x.displacement for x in group[:4]),
            )
            if any(c["_signature"] == signature for c in clusters):
                continue
            clusters.append({
                "_signature": signature,
                "kind": kind,
                "base_register": base,
                "start_va": f"0x{group[0].va:08X}",
                "end_va": f"0x{group[min(len(group), 4) - 1].va:08X}",
                "displacements": [
                    f"{x.displacement:+#x}" for x in group[:4]
                ],
                "instructions": [
                    {
                        "va": f"0x{x.va:08X}",
                        "mnemonic": x.mnemonic,
                        "op_str": x.op_str,
                        "access": x.access,
                    }
                    for x in group[:4]
                ],
                "status": "candidate-only",
            })

    for c in clusters:
        c.pop("_signature", None)
    clusters.sort(key=lambda c: (c["start_va"], c["base_register"]))
    return clusters


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Find candidate original player transform fields for ReXtreme Replay"
    )
    ap.add_argument("ams", type=Path)
    ap.add_argument("--start-va", action="append", default=[], type=parse_int)
    ap.add_argument("--length", type=parse_int, default=0x800)
    ap.add_argument("--frame-audit", type=Path)
    ap.add_argument("--out", type=Path, default=Path("replay-transform-audit.json"))
    ns = ap.parse_args()

    try:
        path = ns.ams.resolve()
        data = path.read_bytes()
        image_base, timestamp, size_of_image, sections = parse_pe(data)

        starts = list(ns.start_va)
        if not starts:
            starts.extend(image_base + rva for rva in DEFAULT_SEED_RVAS)
        starts.extend(frame_audit_sites(ns.frame_audit))

        ranges = normalize_ranges(
            starts,
            ns.length,
            image_base,
            size_of_image,
        )

        access_rows: list[MemoryAccess] = []
        range_reports: list[dict] = []
        for start_va, length in ranges:
            rows = disassemble_accesses(
                data, image_base, sections, start_va, length
            )
            access_rows.extend(rows)
            range_reports.append({
                "start_va": f"0x{start_va:08X}",
                "length": length,
                "memory_access_count": len(rows),
            })

        clusters = cluster_accesses(access_rows)

        report = {
            "format": "rextreme-replay-transform-audit",
            "version": 1,
            "build": "1.7.3.8-x86",
            "rule": (
                "All output is candidate-only. A Replay binding may be promoted only "
                "after exact runtime/disassembly verification of the complete pointer chain "
                "and semantic meaning."
            ),
            "ams": str(path),
            "sha256": sha256(path),
            "pe": {
                "image_base": f"0x{image_base:08X}",
                "time_date_stamp": f"0x{timestamp:08X}",
                "size_of_image": f"0x{size_of_image:08X}",
            },
            "ranges": range_reports,
            "candidate_clusters": clusters,
            "memory_accesses": [
                {
                    **asdict(row),
                    "va": f"0x{row.va:08X}",
                    "displacement": f"{row.displacement:+#x}",
                    "status": "candidate-only",
                }
                for row in access_rows
            ],
            "verified_bindings": [],
        }

        ns.out.parent.mkdir(parents=True, exist_ok=True)
        ns.out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"[OK] wrote {ns.out}")
        print(
            json.dumps(
                {
                    "ranges": len(ranges),
                    "memory_accesses": len(access_rows),
                    "candidate_clusters": len(clusters),
                },
                indent=2,
            )
        )
        return 0

    except (OSError, json.JSONDecodeError, ValueError, struct.error, AuditError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
