#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

CONTROLLER_OFF = 0x005FC518
CONTROLLER_ORIG = bytes.fromhex("8B 4E 08 83 EC")
CONTROLLER_PATCH = bytes.fromhex("E9 D3 50 05 00")

STUB_OFF = 0x006515F0

STUB_ORIG = bytes.fromhex(
    "55 8B EC 6A FF 68 00 CD 3E 01 64 A1 00 00 00 00 "
    "50 81 EC BC 00 00 00 A1 00 7A 89 01 33 C5 89 45 F0 "
    "53 56 57 50 8D 45 F4 64 A3 00 00 00 00 8B C1 89 45 "
    "E8 8B 0D 90 89 94 01 C7 45 FC 00 00 00 00 C7 85 58 "
    "FF FF FF 90 CE A5 00 89 85 54 FF FF FF E8 6B AE A7 "
    "FF 8B C8 E8 C4 66 E2 FF 50 8D 85 54 FF FF FF 50 8D "
    "85 58 FF FF FF 50 E8 30 F0 E2 FF A1 94 DD 93 01 83 "
    "C4 0C A8 01 75 30 83 C8 01 C7 05 90 DD 93 01 0F 00 "
    "00 00 68 70 98 4D 01 A3 94 DD 93 01 C7 05 8C DD 93 "
    "01 00 00 00 00 C6 05 7C DD 93 01 00 E8 CA 60 8C 00 "
    "83 C4 04 FF B5 54 FF FF FF 83 EC 18 8B CC 89 A5 4C "
    "FF FF FF C7 41 10 00 00 00 00 83 BD 58 FF FF FF 00 "
    "75 09 C7 41 10 00 00 00 00 EB"
)

# Historical Phase38 fake-success prefix. The new adapter may safely replace
# this exact known experiment, but never an unknown stub.
PHASE38_PREFIX = bytes.fromhex(
    "8B 56 08 85 D2 74 44 83 EC 14 31 C0 89 04 24 8B "
    "42 50 89 44 24 04 8B 42 54 89 44 24 08 85 C0 74 "
    "04 F0 FF 40 04 C7 44 24 0C 00 00 00 00 C7 44 24 "
    "10 00 00 00 00 8D 04 24 50 89 F1 E8 60 48 FC FF "
    "8D 0C 24 E8 68 FE F9 FF 83 C4 14 E9 0B AF FA FF"
)

STUB_PATCH = bytes.fromhex(
    "53 57 83 EC 30 89 F3 8B 43 08 85 C0 74 47 8B 48 "
    "50 85 C9 74 3C 89 0C 24 31 C0 89 44 24 04 89 44 "
    "24 08 89 44 24 0C 89 44 24 10 89 44 24 14 89 44 "
    "24 18 8D 0C 24 68 01 55 DE C0 E8 00 00 00 00 58 "
    "05 05 7E AD 00 FF 10 85 C0 0F 95 C0 0F B6 F8 EB "
    "08 31 FF EB 04 31 FF EB 33 31 C0 85 FF 0F 94 C0 "
    "89 44 24 1C 8B 53 08 8B 42 50 89 44 24 20 8B 42 "
    "54 89 44 24 24 31 C0 89 44 24 28 89 44 24 2C 8D "
    "44 24 1C 50 8B 4B 28 E8 A4 33 FA FF 8B 73 0C C7 "
    "43 08 00 00 00 00 C7 43 0C 00 00 00 00 85 F6 74 "
    "2A 83 CF FF 8D 46 04 89 F9 F0 0F C1 08 85 C9 75 "
    "1A 8B 06 89 F1 FF 50 04 8D 46 08 89 FA F0 0F C1 "
    "10 4A 75 07 8B 06 89 F1 FF 50 08 83 C4 30 5F 5B "
    "E9 86 AE FA FF"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fmt(data: bytes) -> str:
    return " ".join(f"{x:02X}" for x in data)


def apply(root: Path) -> int:
    pkg = root / "_PACKAGE_PHASE5"
    ams = pkg / "AMS.exe"
    store = pkg / "CampaignStore.dat"
    prebuilt = root / "prebuilt" / "campaign-core" / "IGPLib_x86.dll"
    target_core = pkg / "IGPLib_x86.dll"

    for required in (ams, store, prebuilt):
        if not required.is_file():
            raise FileNotFoundError(f"required file missing: {required}")

    data = bytearray(ams.read_bytes())
    controller = bytes(data[CONTROLLER_OFF:CONTROLLER_OFF + 5])
    current_stub = bytes(data[STUB_OFF:STUB_OFF + len(STUB_PATCH)])

    if controller == CONTROLLER_PATCH and current_stub == STUB_PATCH:
        shutil.copy2(prebuilt, target_core)
        print("[OK] Campaign Store Adapter v1 already active; Core refreshed.")
        return 0

    if controller not in (CONTROLLER_ORIG, CONTROLLER_PATCH):
        raise RuntimeError(
            "OnlinePurchase controller has unknown bytes: " + fmt(controller)
        )

    known_stub = current_stub == STUB_ORIG
    phase38_stub = (
        current_stub[:len(PHASE38_PREFIX)] == PHASE38_PREFIX
        and current_stub[len(PHASE38_PREFIX):] == STUB_ORIG[len(PHASE38_PREFIX):]
    )
    if not known_stub and not phase38_stub:
        raise RuntimeError(
            "OnlinePurchase retired stub has unknown bytes; refusing overwrite. "
            f"prefix={fmt(current_stub[:24])}"
        )

    before = hashlib.sha256(data).hexdigest()
    backup_dir = root / "_BACKUPS" / "CAMPAIGN-STORE-ADAPTER-V1"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"AMS.{before}.bak"
    if not backup.exists():
        shutil.copy2(ams, backup)

    # Redirect the controller before the old Start call. At this point ESI is
    # still AsphaltShop*, which the local stub intentionally consumes.
    data[CONTROLLER_OFF:CONTROLLER_OFF + 5] = CONTROLLER_PATCH
    data[STUB_OFF:STUB_OFF + len(STUB_PATCH)] = STUB_PATCH

    tmp = ams.with_suffix(".store-adapter.tmp")
    tmp.write_bytes(data)

    verify = tmp.read_bytes()
    if verify[CONTROLLER_OFF:CONTROLLER_OFF + 5] != CONTROLLER_PATCH:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("controller verification failed")
    if verify[STUB_OFF:STUB_OFF + len(STUB_PATCH)] != STUB_PATCH:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("stub verification failed")

    tmp.replace(ams)
    shutil.copy2(prebuilt, target_core)

    trace = root / "_TRACE_MONTAR"
    trace.mkdir(parents=True, exist_ok=True)
    report = trace / "CAMPAIGN-STORE-ADAPTER-V1.json"
    payload = {
        "phase": "Campaign Store Adapter v1",
        "controller_va": "0x009FD118",
        "controller_file_offset": "0x005FC518",
        "local_stub_va": "0x00A521F0",
        "local_stub_file_offset": "0x006515F0",
        "selector": "0xC0DE5501",
        "legacy_endpoint": "scripts/general/buy_item.php",
        "legacy_endpoint_reachable_from_purchase": False,
        "old_result_business_callback_called": False,
        "ui_signal": "0x009F5620",
        "request_cleanup": "local stub clears/releases AsphaltShop+0x08/+0x0C",
        "offer_key": "FNV1a(item_key) & 0x7fffffff",
        "catalog": str(store),
        "backup": str(backup),
        "sha256_before": before,
        "sha256_after": sha256(ams),
        "core_sha256": sha256(target_core),
        "normalized_phase38_fake_success": phase38_stub,
    }
    report.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("[OK] Campaign Store Adapter v1 applied.")
    print(f"[AMS] {payload['sha256_after']}")
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
