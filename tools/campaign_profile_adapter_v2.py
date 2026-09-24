#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ONLINE_OFF = 0x00BACDD0
ONLINE_FALSE = bytes.fromhex("31 C0 C3 90 90 90 90")

POPUP_OFF = 0x009168B0
POPUP_ORIG = bytes.fromhex("55 8B EC 6A FF")
POPUP_SAFE = bytes.fromhex("31 C0 C2 18 00")

SYNC_SUBMIT_OFF = 0x008D3A02
SYNC_SUBMIT_ORIG = bytes.fromhex(
    "C7 47 48 01 00 00 00 "
    "8B 0D D0 A1 93 01 "
    "E8 1C 5F AB FF "
    "8B F0 8D 45 EC"
)
SYNC_SUBMIT_V1 = bytes.fromhex(
    "C7 47 48 01 00 00 00 "
    "6A 00 "
    "6A 00 "
    "8B CF "
    "E8 4C 7F 00 00 "
    "E9 6A 00 00 00"
)

PATCHES = (
    ("native profile validation path 1", 0x0069B8C6,
     bytes.fromhex("74 24"), bytes.fromhex("74 22")),
    ("native profile validation path 2", 0x0069B8E6,
     bytes.fromhex("32 C0"), bytes.fromhex("B0 01")),
    ("STR_MENU_SYNC_LOADING site 1", 0x00685F9C,
     bytes.fromhex("0F 84 DF 00 00 00"), bytes.fromhex("E9 E0 00 00 00 90")),
    ("runtime profile sync pending flag", 0x006CF957,
     bytes.fromhex("8D 45 E0 0F 57 C0 50 66 0F"),
     bytes.fromhex("C6 47 4C 00 E9 43 01 00 00")),
    ("startup profile sync state machine", 0x0092B82A,
     bytes.fromhex("0F 84 8D 01 00 00"),
     bytes.fromhex("E9 8E 01 00 00 90")),
)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def fmt(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)

def patch_one(data: bytearray, label: str, off: int, before: bytes, after: bytes, changes: list[dict]) -> None:
    cur = bytes(data[off:off+len(before)])
    if cur == after:
        changes.append({"label": label, "offset": f"0x{off:08X}", "status": "already-patched"})
        return
    if cur != before:
        raise RuntimeError(f"{label}: unknown bytes at 0x{off:08X}: {fmt(cur)}")
    data[off:off+len(before)] = after
    changes.append({"label": label, "offset": f"0x{off:08X}", "status": "patched",
                    "before": fmt(before), "after": fmt(after)})

def apply_bytes(data: bytearray) -> list[dict]:
    if bytes(data[ONLINE_OFF:ONLINE_OFF+len(ONLINE_FALSE)]) != ONLINE_FALSE:
        raise RuntimeError("Global IsOnline must remain FALSE")

    changes: list[dict] = []

    # Profile Adapter v1 introduced this broad GlobalSync completion hook.
    # Runtime testing showed it can crash during the Gameloft splash.
    # v2 explicitly removes it and preserves the original submit routine.
    cur_sync = bytes(data[SYNC_SUBMIT_OFF:SYNC_SUBMIT_OFF+len(SYNC_SUBMIT_ORIG)])
    if cur_sync == SYNC_SUBMIT_V1:
        data[SYNC_SUBMIT_OFF:SYNC_SUBMIT_OFF+len(SYNC_SUBMIT_ORIG)] = SYNC_SUBMIT_ORIG
        changes.append({
            "label": "retire v1 broad GlobalSync completion hook",
            "offset": f"0x{SYNC_SUBMIT_OFF:08X}",
            "status": "restored-original",
            "before": fmt(SYNC_SUBMIT_V1),
            "after": fmt(SYNC_SUBMIT_ORIG),
        })
    elif cur_sync == SYNC_SUBMIT_ORIG:
        changes.append({
            "label": "preserve original GlobalSync submit",
            "offset": f"0x{SYNC_SUBMIT_OFF:08X}",
            "status": "original-preserved",
        })
    else:
        raise RuntimeError("GlobalSync submit has unknown bytes: " + fmt(cur_sync))

    for row in PATCHES:
        patch_one(data, *row, changes)

    popup = bytes(data[POPUP_OFF:POPUP_OFF+len(POPUP_ORIG)])
    if popup == POPUP_ORIG:
        data[POPUP_OFF:POPUP_OFF+len(POPUP_SAFE)] = POPUP_SAFE
        changes.append({"label": "obsolete sync/network popup wrapper",
                        "offset": f"0x{POPUP_OFF:08X}", "status": "patched"})
    elif popup == POPUP_SAFE:
        changes.append({"label": "obsolete sync/network popup wrapper",
                        "offset": f"0x{POPUP_OFF:08X}", "status": "already-patched"})
    else:
        raise RuntimeError("popup wrapper has unknown bytes: " + fmt(popup))

    return changes

def apply(root: Path) -> int:
    ams = root / "_PACKAGE_PHASE5" / "AMS.exe"
    if not ams.is_file():
        raise FileNotFoundError(f"AMS.exe not found: {ams}")

    raw = ams.read_bytes()
    before = sha(raw)
    data = bytearray(raw)
    changes = apply_bytes(data)

    backup_dir = root / "_BACKUPS" / "CAMPAIGN-PROFILE-V2"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"AMS.exe.{before}.bak"
    if not backup.exists():
        shutil.copy2(ams, backup)

    tmp = ams.with_suffix(".profile-v2.tmp")
    tmp.write_bytes(data)
    verify = tmp.read_bytes()

    if verify[ONLINE_OFF:ONLINE_OFF+len(ONLINE_FALSE)] != ONLINE_FALSE:
        raise RuntimeError("verification failed: IsOnline")
    if verify[SYNC_SUBMIT_OFF:SYNC_SUBMIT_OFF+len(SYNC_SUBMIT_ORIG)] != SYNC_SUBMIT_ORIG:
        raise RuntimeError("verification failed: GlobalSync submit")
    for label, off, _before, after in PATCHES:
        if verify[off:off+len(after)] != after:
            raise RuntimeError(f"verification failed: {label}")
    if verify[POPUP_OFF:POPUP_OFF+len(POPUP_SAFE)] != POPUP_SAFE:
        raise RuntimeError("verification failed: popup wrapper")

    tmp.replace(ams)
    after = sha(ams.read_bytes())

    trace = root / "_TRACE_MONTAR"
    trace.mkdir(parents=True, exist_ok=True)
    report_path = trace / "CAMPAIGN-PROFILE-V2.json"
    report_path.write_text(json.dumps({
        "phase": "Campaign Profile Adapter v2",
        "logical_connectivity": "offline/false",
        "profile_validation": "local",
        "known_sync_loading_sites_neutralized": 3,
        "runtime_pending_sync": "consumed locally",
        "global_sync_submit": "original/preserved",
        "v1_broad_completion_hook": "retired",
        "sha256_before": before,
        "sha256_after": after,
        "backup": str(backup),
        "changes": changes,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[OK] Campaign Profile Adapter v2 applied.")
    print("[PROFILE] STR_MENU_SYNC_LOADING sites neutralized: 3 / 3")
    print("[PROFILE] GlobalSync broad completion hook: RETIRED")
    print("[PROFILE] Global IsOnline: FALSE")
    print(f"[AMS] {after}")
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
