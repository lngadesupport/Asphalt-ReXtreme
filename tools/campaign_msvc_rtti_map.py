#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

IMAGE_SCN_MEM_EXECUTE = 0x20000000


class PE32:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        self.sections: list[dict] = []

        if self.data[:2] != b"MZ":
            raise ValueError("not an MZ executable")

        pe = self.u32(0x3C)
        if self.data[pe:pe + 4] != b"PE\0\0":
            raise ValueError("invalid PE signature")

        number_of_sections = self.u16(pe + 6)
        optional_size = self.u16(pe + 20)
        optional = pe + 24

        if self.u16(optional) != 0x010B:
            raise ValueError("expected PE32")

        self.image_base = self.u32(optional + 28)
        section_table = optional + optional_size

        for i in range(number_of_sections):
            off = section_table + i * 40
            name = self.data[off:off + 8].split(b"\0", 1)[0].decode("ascii", "replace")
            virtual_size = self.u32(off + 8)
            virtual_address = self.u32(off + 12)
            raw_size = self.u32(off + 16)
            raw_offset = self.u32(off + 20)
            characteristics = self.u32(off + 36)
            self.sections.append({
                "name": name,
                "va": virtual_address,
                "size": max(virtual_size, raw_size),
                "raw_size": raw_size,
                "raw_offset": raw_offset,
                "characteristics": characteristics,
            })

    def u16(self, off: int) -> int:
        return struct.unpack_from("<H", self.data, off)[0]

    def u32(self, off: int) -> int:
        return struct.unpack_from("<I", self.data, off)[0]

    def off_to_va(self, off: int) -> int | None:
        for sec in self.sections:
            ro = sec["raw_offset"]
            rs = sec["raw_size"]
            if ro <= off < ro + rs:
                return self.image_base + sec["va"] + (off - ro)
        return None

    def va_to_off(self, va: int) -> int | None:
        rva = va - self.image_base
        for sec in self.sections:
            if sec["va"] <= rva < sec["va"] + sec["raw_size"]:
                return sec["raw_offset"] + (rva - sec["va"])
        return None

    def is_executable_va(self, va: int) -> bool:
        rva = va - self.image_base
        for sec in self.sections:
            if sec["va"] <= rva < sec["va"] + sec["size"]:
                return bool(sec["characteristics"] & IMAGE_SCN_MEM_EXECUTE)
        return False

    def find_all(self, needle: bytes):
        pos = 0
        while True:
            pos = self.data.find(needle, pos)
            if pos < 0:
                return
            yield pos
            pos += 1


def decorated_name(name: str) -> str:
    if name.startswith(".?A"):
        return name
    if "::" in name:
        parts = name.split("::")
        cls = parts[-1]
        namespaces = "@".join(reversed(parts[:-1]))
        return f".?AV{cls}@{namespaces}@@"
    return f".?AV{name}@@"


def map_class(pe: PE32, requested: str, max_methods: int) -> dict:
    name = decorated_name(requested)
    needle = name.encode("ascii") + b"\0"
    matches = []

    for string_off in pe.find_all(needle):
        # MSVC x86 TypeDescriptor:
        #   +0 pVFTable
        #   +4 spare
        #   +8 decorated name
        td_off = string_off - 8
        td_va = pe.off_to_va(td_off)
        if td_va is None:
            continue

        col_candidates = []
        for ref_off in pe.find_all(struct.pack("<I", td_va)):
            # CompleteObjectLocator::pTypeDescriptor lives at +0x0C.
            col_off = ref_off - 12
            col_va = pe.off_to_va(col_off)
            if col_va is None:
                continue

            # Basic x86 COL sanity.
            try:
                signature = pe.u32(col_off)
                offset = pe.u32(col_off + 4)
                cd_offset = pe.u32(col_off + 8)
                class_hierarchy = pe.u32(col_off + 16)
            except struct.error:
                continue

            if signature not in (0, 1):
                continue
            if class_hierarchy == 0:
                continue

            col_candidates.append((col_off, col_va, offset, cd_offset))

        for col_off, col_va, offset, cd_offset in col_candidates:
            for col_ref_off in pe.find_all(struct.pack("<I", col_va)):
                # MSVC vftable[-1] points to the CompleteObjectLocator.
                vtable_off = col_ref_off + 4
                vtable_va = pe.off_to_va(vtable_off)
                if vtable_va is None:
                    continue

                methods = []
                off = vtable_off
                for _ in range(max_methods):
                    if off + 4 > len(pe.data):
                        break
                    target = pe.u32(off)
                    if not pe.is_executable_va(target):
                        break
                    methods.append(target)
                    off += 4

                if not methods:
                    continue

                matches.append({
                    "decorated_name": name,
                    "string_file_offset": f"0x{string_off:08X}",
                    "type_descriptor_va": f"0x{td_va:08X}",
                    "complete_object_locator_va": f"0x{col_va:08X}",
                    "object_offset": offset,
                    "constructor_displacement": cd_offset,
                    "vtable_va": f"0x{vtable_va:08X}",
                    "methods": [f"0x{x:08X}" for x in methods],
                })

    # Deduplicate multiple raw references that resolve to the same table.
    unique = {}
    for item in matches:
        unique[item["vtable_va"]] = item

    return {
        "requested": requested,
        "decorated_name": name,
        "matches": list(unique.values()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Map MSVC x86 RTTI classes and vtables in AMS.exe")
    ap.add_argument("binary", type=Path)
    ap.add_argument("classes", nargs="+")
    ap.add_argument("--max-methods", type=int, default=64)
    ap.add_argument("-o", "--output", type=Path)
    ns = ap.parse_args()

    pe = PE32(ns.binary)
    report = {
        "binary": str(ns.binary),
        "image_base": f"0x{pe.image_base:08X}",
        "classes": [map_class(pe, q, ns.max_methods) for q in ns.classes],
    }

    text = json.dumps(report, indent=2, ensure_ascii=False)
    if ns.output:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        ns.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
