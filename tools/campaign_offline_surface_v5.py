#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path

ONLINE_OFF = 0x00BACDD0
ONLINE_FALSE = bytes.fromhex("31 C0 C3 90 90 90 90")

POPUP_OFF = 0x009168B0
POPUP_ORIG = bytes.fromhex("55 8B EC 6A FF")
FILTER_LEN = 47

PROFILE_PATCHES = (
    ("local profile validation path 1", 0x0069B8C6,
     bytes.fromhex("74 24"), bytes.fromhex("74 22")),
    ("local profile validation path 2", 0x0069B8E6,
     bytes.fromhex("32 C0"), bytes.fromhex("B0 01")),
    ("startup remote-profile sync gate", 0x0092B82A,
     bytes.fromhex("0F 84 8D 01 00 00 00")[:6],
     bytes.fromhex("E9 8E 01 00 00 90")),
)

# Keep onboarding on its existing native success continuations.
ONBOARDING_PATCHES = (
    ("age/gender gate 1 -> local success", 0x006A1CE1,
     bytes.fromhex("0F 85 FE 00 00 00"), bytes.fromhex("E9 FF 00 00 00 90")),
    ("age/gender gate 2 -> local success", 0x006A1E03,
     bytes.fromhex("0F 85 D8 00 00 00"), bytes.fromhex("E9 D9 00 00 00 90")),
)

# Areas already reserved/used by Campaign adapters. Do not allocate the popup filter here.
PROTECTED_CAVES = (
    (0x00469380, 0x00469440),  # Garage / old Phase35/48 family
    (0x00CE8F60, 0x00CE9030),  # Career finish bridge
    (0x00D091A0, 0x00D09240),  # Career v1 begin bridge
)

NETWORK_MARKERS = (
    b"STR_POPUP_NO_INTERNET_TITLE",
    b"STR_POPUP_NO_INTERNET_DESCRIPTION",
    b"STR_MENU_SYNC_LOADING",
    b"NO_INTERNET",
    b"CONNECTION_FAILED",
    b"CONNECTION_LOST",
    b"CONNECTION_UNAVAILABLE",
    b"TRY_AGAIN",
)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def fmt(data: bytes) -> str:
    return " ".join(f"{x:02X}" for x in data)

def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]

def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]

def i32(data: bytes, off: int) -> int:
    return struct.unpack_from("<i", data, off)[0]

def parse_pe(data: bytes):
    pe = u32(data, 0x3C)
    if data[pe:pe+4] != b"PE\0\0":
        raise RuntimeError("invalid PE")
    sec_count = u16(data, pe + 6)
    opt_size = u16(data, pe + 20)
    opt = pe + 24
    if u16(data, opt) != 0x10B:
        raise RuntimeError("expected x86 PE32")
    image_base = u32(data, opt + 28)
    sec_off = opt + opt_size
    sections = []
    for i in range(sec_count):
        o = sec_off + i * 40
        sections.append({
            "name": data[o:o+8].split(b"\0", 1)[0].decode("ascii", "replace"),
            "vsize": u32(data, o + 8),
            "rva": u32(data, o + 12),
            "raw_size": u32(data, o + 16),
            "raw": u32(data, o + 20),
            "chars": u32(data, o + 36),
        })
    return image_base, sections

def file_to_va(off: int, image_base: int, sections) -> int:
    for s in sections:
        if s["raw"] <= off < s["raw"] + s["raw_size"]:
            return image_base + s["rva"] + (off - s["raw"])
    raise RuntimeError(f"file offset 0x{off:X} is not mapped")

def va_to_file(va: int, image_base: int, sections) -> int | None:
    rva = va - image_base
    for s in sections:
        span = max(s["vsize"], s["raw_size"])
        if s["rva"] <= rva < s["rva"] + span:
            return s["raw"] + (rva - s["rva"])
    return None

def rel32(src_va: int, instr_len: int, dst_va: int) -> bytes:
    return struct.pack("<i", dst_va - (src_va + instr_len))

def overlaps_protected(start: int, end: int) -> bool:
    return any(start < b and end > a for a, b in PROTECTED_CAVES)

def find_exec_cave(data: bytes, sections, length: int = FILTER_LEN) -> int:
    candidates = []
    for s in sections:
        if not (s["chars"] & 0x20000000):  # IMAGE_SCN_MEM_EXECUTE
            continue
        a = s["raw"]
        b = min(len(data), a + s["raw_size"])
        i = a
        while i + length <= b:
            p = data.find(b"\xCC" * length, i, b)
            if p < 0:
                break
            # Prefer a larger CC island so future patch bytes do not touch real code.
            left = p
            while left > a and data[left-1] == 0xCC:
                left -= 1
            right = p + length
            while right < b and data[right] == 0xCC:
                right += 1
            if not overlaps_protected(p, p + length):
                candidates.append((right - left, p))
            i = max(p + 1, right)
    if not candidates:
        raise RuntimeError("no safe executable 0xCC cave found for popup filter")
    # Pick the largest available island, then the highest file offset.
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][1]

def build_popup_filter(cave_va: int, popup_va: int) -> bytes:
    code = bytearray()
    code += bytes.fromhex("8B 44 24 04")        # mov eax,[esp+4] ; title wrapper*
    code += bytes.fromhex("8B 00")              # mov eax,[eax]
    code += bytes.fromhex("85 C0")              # test eax,eax
    code += bytes.fromhex("74 1B")              # jz original
    code += bytes.fromhex("8B 00")              # mov eax,[eax] ; buffer header*
    code += bytes.fromhex("85 C0")
    code += bytes.fromhex("74 15")
    code += bytes.fromhex("81 78 01 53 54 52 5F")  # "STR_"
    code += bytes.fromhex("75 0C")
    code += bytes.fromhex("81 78 0E 49 4E 54 45")  # "INTE"
    code += bytes.fromhex("75 03")
    code += bytes.fromhex("C2 18 00")            # suppress NO_INTERNET popup
    code += POPUP_ORIG                           # replay overwritten prologue
    jmp_va = cave_va + len(code)
    code += b"\xE9" + rel32(jmp_va, 5, popup_va + len(POPUP_ORIG))
    if len(code) != FILTER_LEN:
        raise RuntimeError(f"popup filter size mismatch: {len(code)}")
    return bytes(code)

def patch_one(data: bytearray, label: str, off: int, before: bytes, after: bytes, changes: list[dict]):
    cur = bytes(data[off:off+len(before)])
    if cur == after:
        changes.append({"label": label, "offset": f"0x{off:08X}", "status": "already-patched"})
        return
    if cur != before:
        raise RuntimeError(f"{label}: unknown bytes at 0x{off:08X}: {fmt(cur)}")
    data[off:off+len(before)] = after
    changes.append({
        "label": label, "offset": f"0x{off:08X}", "status": "patched",
        "before": fmt(before), "after": fmt(after),
    })

def detect_existing_filter(data: bytes, image_base: int, sections):
    cur = data[POPUP_OFF:POPUP_OFF+5]
    if len(cur) == 5 and cur[0] == 0xE9:
        popup_va = file_to_va(POPUP_OFF, image_base, sections)
        target_va = popup_va + 5 + i32(cur, 1)
        target_off = va_to_file(target_va, image_base, sections)
        if target_off is not None and 0 <= target_off <= len(data) - FILTER_LEN:
            expected = build_popup_filter(target_va, popup_va)
            if data[target_off:target_off+FILTER_LEN] == expected:
                return target_off, target_va
    return None

def apply_bytes(data: bytearray):
    if bytes(data[ONLINE_OFF:ONLINE_OFF+len(ONLINE_FALSE)]) != ONLINE_FALSE:
        raise RuntimeError("Global IsOnline must remain FALSE")

    image_base, sections = parse_pe(data)
    popup_va = file_to_va(POPUP_OFF, image_base, sections)
    changes = []

    for row in PROFILE_PATCHES:
        patch_one(data, *row, changes)
    for row in ONBOARDING_PATCHES:
        patch_one(data, *row, changes)

    existing = detect_existing_filter(data, image_base, sections)
    if existing:
        cave_off, cave_va = existing
        changes.append({
            "label": "central NO_INTERNET popup filter",
            "offset": f"0x{POPUP_OFF:08X}",
            "cave_offset": f"0x{cave_off:08X}",
            "status": "already-patched",
        })
        return changes, cave_off, cave_va

    if bytes(data[POPUP_OFF:POPUP_OFF+5]) != POPUP_ORIG:
        raise RuntimeError(
            "GS_MessagePopup entry is not pristine and is not the v5 central filter: "
            + fmt(bytes(data[POPUP_OFF:POPUP_OFF+5]))
        )

    cave_off = find_exec_cave(bytes(data), sections)
    cave_va = file_to_va(cave_off, image_base, sections)
    filter_code = build_popup_filter(cave_va, popup_va)
    if bytes(data[cave_off:cave_off+FILTER_LEN]) != b"\xCC" * FILTER_LEN:
        raise RuntimeError("selected popup-filter cave is not pristine")

    hook = b"\xE9" + rel32(popup_va, 5, cave_va)
    data[cave_off:cave_off+FILTER_LEN] = filter_code
    data[POPUP_OFF:POPUP_OFF+5] = hook
    changes.append({
        "label": "central NO_INTERNET popup filter",
        "offset": f"0x{POPUP_OFF:08X}",
        "cave_offset": f"0x{cave_off:08X}",
        "cave_va": f"0x{cave_va:08X}",
        "status": "patched",
        "behavior": "suppress STR_POPUP_NO_INTERNET_TITLE only; preserve all other GS_MessagePopup calls",
    })
    return changes, cave_off, cave_va

def marker_inventory(data: bytes):
    out = []
    for marker in NETWORK_MARKERS:
        hits = []
        start = 0
        while True:
            p = data.find(marker, start)
            if p < 0:
                break
            hits.append(f"0x{p:08X}")
            start = p + 1
        if hits:
            out.append({"marker": marker.decode("ascii", "replace"), "occurrences": len(hits), "offsets": hits[:64]})
    return out

def apply(root: Path):
    ams = root / "_PACKAGE_PHASE5" / "AMS.exe"
    if not ams.is_file():
        raise FileNotFoundError(ams)

    raw = ams.read_bytes()
    before = sha(raw)
    data = bytearray(raw)
    changes, cave_off, cave_va = apply_bytes(data)

    bdir = root / "_BACKUPS" / "CAMPAIGN-PROFILE-V5"
    bdir.mkdir(parents=True, exist_ok=True)
    bak = bdir / f"AMS.exe.{before}.bak"
    if not bak.exists():
        shutil.copy2(ams, bak)

    tmp = ams.with_suffix(".profile-v5.tmp")
    tmp.write_bytes(data)
    verify = tmp.read_bytes()

    image_base, sections = parse_pe(verify)
    if verify[ONLINE_OFF:ONLINE_OFF+len(ONLINE_FALSE)] != ONLINE_FALSE:
        raise RuntimeError("verification failed: IsOnline")
    for label, off, _before, after in PROFILE_PATCHES + ONBOARDING_PATCHES:
        if verify[off:off+len(after)] != after:
            raise RuntimeError(f"verification failed: {label}")
    if not detect_existing_filter(verify, image_base, sections):
        raise RuntimeError("verification failed: central popup filter")

    tmp.replace(ams)
    after = sha(ams.read_bytes())
    inventory = marker_inventory(ams.read_bytes())

    trace = root / "_TRACE_MONTAR"
    trace.mkdir(parents=True, exist_ok=True)
    report = {
        "phase": "Campaign Offline Surface Adapter v5",
        "logical_connectivity": "offline/false",
        "startup_remote_profile_gate": "retired",
        "onboarding_connectivity": "local-success continuations",
        "no_internet_popup": {
            "policy": "centrally suppressed at GS_MessagePopup",
            "target_key": "STR_POPUP_NO_INTERNET_TITLE",
            "other_popups_preserved": True,
            "hook_file_offset": f"0x{POPUP_OFF:08X}",
            "cave_file_offset": f"0x{cave_off:08X}",
            "cave_va": f"0x{cave_va:08X}",
        },
        "network_marker_inventory": inventory,
        "note": "String presence is inventory only; online consumers/transports are removed in subsequent hardening gates.",
        "sha256_before": before,
        "sha256_after": after,
        "backup": str(bak),
        "changes": changes,
    }
    report_path = trace / "CAMPAIGN-OFFLINE-SURFACE-V5.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[OK] Campaign Offline Surface Adapter v5 applied.")
    print("[PROFILE] startup remote-profile gate: RETIRED")
    print("[ONBOARDING] connectivity branches: LOCAL")
    print("[POPUP] STR_POPUP_NO_INTERNET_TITLE: centrally suppressed")
    print("[NETWORK] Global IsOnline: FALSE")
    print(f"[CAVE] 0x{cave_off:08X} / VA 0x{cave_va:08X}")
    print(f"[AMS] {after}")
    print(f"[REPORT] {report_path}")
    return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    ns = ap.parse_args()
    try:
        return apply(Path(ns.project_root).resolve())
    except Exception as exc:
        print(f"[ERRO] {exc}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
