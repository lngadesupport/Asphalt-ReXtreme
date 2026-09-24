#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path

IMAGE_BASE = 0x00400000
IGP_HTTPPOST_IAT_RVA = 0x0112A034
IGP_HTTPPOST_PREF_VA = IMAGE_BASE + IGP_HTTPPOST_IAT_RVA

UPGRADE_LEGACY_MAGIC = 0xC0DE4402

SITE_VA = 0x009A0930
SITE_OFF = 0x0059FD30

ORIGINAL = bytes.fromhex(
    "55 8B EC 6A FF 68 F9 B5 3D 01 64 A1 00 00 00 00 "
    "50 83 EC 58 A1 00 7A 89 01 33 C5 89 45 F0 53 56 "
    "57 50 8D 45 F4 64 A3 00 00 00 00 8B F1 8B 7D 08 "
    "89 7D AC C7 45 B4 00 00 00 00 83 7E 70 00 C7 45 "
    "FC 01 00 00 00 0F 85 DC 01 00 00 83 BE 80 00 00 "
    "00 00 0F 85 CF 01 00 00 83 BE C0 00 00 00 00 0F "
    "85 C2 01 00 00 83 BE 90 00 00 00 00 0F 85 B5 01 "
    "00 00 83 BE A0 00 00 00 00 8D 9E A0 00 00 00 89 "
    "5D B0 0F 85 9F 01 00 00 83 BE B0 00 00 00"
)


def fmt(data: bytes) -> str:
    return " ".join(f"{x:02X}" for x in data)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_pe32_x86(data: bytes) -> None:
    if data[:2] != b"MZ":
        raise RuntimeError("AMS.exe is not MZ")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise RuntimeError("invalid PE signature")
    if struct.unpack_from("<H", data, pe + 4)[0] != 0x014C:
        raise RuntimeError("expected x86 image")
    opt = pe + 24
    if struct.unpack_from("<H", data, opt)[0] != 0x010B:
        raise RuntimeError("expected PE32")
    if struct.unpack_from("<I", data, opt + 28)[0] != IMAGE_BASE:
        raise RuntimeError("unexpected preferred image base")


def patch_rel32(code: bytearray, at: int, dst_va: int) -> None:
    src_next = SITE_VA + at + 6
    struct.pack_into("<i", code, at + 2, dst_va - src_next)


def build_stub() -> bytes:
    code = bytearray()

    # Preserve the original __thiscall ABI. Stack:
    #   +08 output shared pair*
    #   +0C car_id
    #   +10 old currency selector (ignored by Campaign)
    #   +14 selection object*
    #   +18 selection shared control block*
    code += bytes.fromhex("55 8B EC 53 56 57 83 EC 14")

    # Original caller expects a shared result pair. No remote request exists now.
    code += bytes.fromhex("8B 7D 08")
    code += bytes.fromhex("C7 07 00 00 00 00")
    code += bytes.fromhex("C7 47 04 00 00 00 00")

    # CampaignLegacyUpgradeSelectionArgs at ESP:
    #   car_id, selection_object, status, applied_count, revision
    code += bytes.fromhex("8B 45 0C 89 04 24")
    code += bytes.fromhex("8B 45 14 89 44 24 04")
    code += bytes.fromhex(
        "31 C0 "
        "89 44 24 08 "
        "89 44 24 0C "
        "89 44 24 10"
    )
    code += bytes.fromhex("8D 0C 24")

    # Position-independent call through the existing IGP import gateway.
    code += b"\x68" + struct.pack("<I", UPGRADE_LEGACY_MAGIC)
    call_va = SITE_VA + len(code)
    code += b"\xE8\x00\x00\x00\x00"
    pop_va = call_va + 5
    code += b"\x58"
    code += b"\x05" + struct.pack(
        "<I", (IGP_HTTPPOST_PREF_VA - pop_va) & 0xFFFFFFFF
    )
    code += bytes.fromhex("FF 10")

    # Consume/release the by-value shared control block exactly like the
    # original callee, preventing one ref leak per upgrade click.
    code += bytes.fromhex("8B 75 18 85 F6")
    jz_done = len(code)
    code += bytes.fromhex("0F 84 00 00 00 00")

    code += bytes.fromhex("83 CB FF 8D 4E 04 8B C3 F0 0F C1 01")
    jnz_done1 = len(code)
    code += bytes.fromhex("0F 85 00 00 00 00")

    code += bytes.fromhex(
        "8B 06 8B CE FF 50 04 "
        "8D 56 08 F0 0F C1 1A 4B"
    )
    jnz_done2 = len(code)
    code += bytes.fromhex("0F 85 00 00 00 00")

    code += bytes.fromhex("8B 06 8B CE FF 50 08")

    done = len(code)
    code += bytes.fromhex(
        "8B C7 "
        "83 C4 14 "
        "5F 5E 5B 5D "
        "C2 14 00"
    )

    done_va = SITE_VA + done
    for branch in (jz_done, jnz_done1, jnz_done2):
        patch_rel32(code, branch, done_va)

    if len(code) != len(ORIGINAL):
        raise RuntimeError(
            f"upgrade adapter length changed: {len(code)} != {len(ORIGINAL)}"
        )

    return bytes(code)


PATCHED = build_stub()


def require(data: bytes, off: int, expected: bytes, label: str) -> None:
    current = bytes(data[off:off + len(expected)])
    if current != expected:
        raise RuntimeError(
            f"{label}: unexpected bytes at 0x{off:08X}\n"
            f"current : {fmt(current)}\n"
            f"expected: {fmt(expected)}"
        )


def apply(root: Path) -> int:
    package = root / "_PACKAGE_PHASE5"
    ams = package / "AMS.exe"
    prebuilt_core = root / "prebuilt" / "campaign-core" / "IGPLib_x86.dll"
    target_core = package / "IGPLib_x86.dll"
    upgrades = package / "CampaignUpgrades.dat"
    ui_map = package / "CampaignUpgradeUiMap.dat"

    for required in (ams, prebuilt_core, upgrades, ui_map):
        if not required.is_file():
            raise FileNotFoundError(f"required file missing: {required}")

    data = bytearray(ams.read_bytes())
    validate_pe32_x86(data)

    current = bytes(data[SITE_OFF:SITE_OFF + len(PATCHED)])
    if current == PATCHED:
        shutil.copy2(prebuilt_core, target_core)
        print("[OK] Campaign Upgrade Adapter v1 already active; Core refreshed.")
        return 0

    require(data, SITE_OFF, ORIGINAL, "UpgradeCar manager submit")

    before = hashlib.sha256(data).hexdigest()
    backup_dir = root / "_BACKUPS" / "CAMPAIGN-UPGRADE-ADAPTER-V1"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"AMS.{before}.bak"
    if not backup.exists():
        shutil.copy2(ams, backup)

    data[SITE_OFF:SITE_OFF + len(PATCHED)] = PATCHED

    tmp = ams.with_suffix(".upgrade-adapter.tmp")
    tmp.write_bytes(data)
    verify = tmp.read_bytes()
    require(verify, SITE_OFF, PATCHED, "Upgrade adapter verification")

    tmp.replace(ams)
    shutil.copy2(prebuilt_core, target_core)

    report_dir = root / "_TRACE_MONTAR"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / "CAMPAIGN-UPGRADE-ADAPTER-V1.json"

    payload = {
        "phase": "Campaign Upgrade Adapter v1",
        "site_va": f"0x{SITE_VA:08X}",
        "site_file_offset": f"0x{SITE_OFF:08X}",
        "patch_length": len(PATCHED),
        "selector": f"0x{UPGRADE_LEGACY_MAGIC:08X}",
        "single_direct_caller_verified": "0x00951658",
        "legacy_selection": {
            "object_begin_offset": "0x10",
            "object_end_offset": "0x14",
            "entry_size": 8,
            "ui_action_id_offset": 0,
        },
        "authority": {
            "upgrade_car_php": "retired from user action",
            "old_currency_selector": "ignored",
            "old_balance": "ignored",
            "old_price": "ignored",
            "selection_ids": "read-only presentation metadata",
            "transaction": "Campaign Core / CampaignUpgradeUiMap.dat / CampaignUpgrades.dat",
        },
        "aslr_safe": True,
        "iat_rva": f"0x{IGP_HTTPPOST_IAT_RVA:08X}",
        "sha256_before": before,
        "sha256_after": sha256(ams),
        "core_sha256": sha256(target_core),
        "backup": str(backup),
    }
    report.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("[OK] Campaign Upgrade Adapter v1 applied.")
    print(f"[AMS]  {payload['sha256_after']}")
    print(f"[CORE] {payload['core_sha256']}")
    print(f"[REPORT] {report}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, required=True)
    ns = ap.parse_args()

    try:
        return apply(ns.project_root.resolve())
    except Exception as exc:
        print(f"[ERRO] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
