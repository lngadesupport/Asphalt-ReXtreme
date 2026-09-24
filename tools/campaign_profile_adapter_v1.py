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
SYNC_SUBMIT_LOCAL = bytes.fromhex(
    "C7 47 48 01 00 00 00 "
    "6A 00 "
    "6A 00 "
    "8B CF "
    "E8 4C 7F 00 00 "
    "E9 6A 00 00 00"
)

PATCHES = (
    (
        "native profile: first local validation",
        0x0069B8C6,
        bytes.fromhex("74 24"),
        bytes.fromhex("74 22"),
    ),
    (
        "native profile: secondary validation true",
        0x0069B8E6,
        bytes.fromhex("32 C0"),
        bytes.fromhex("B0 01"),
    ),
    (
        "profile sync loading site 1 -> local continuation",
        0x00685F9C,
        bytes.fromhex("0F 84 DF 00 00 00"),
        bytes.fromhex("E9 E0 00 00 00 90"),
    ),
    (
        "profile sync runtime pending flag -> consume locally",
        0x006CF957,
        bytes.fromhex("8D 45 E0 0F 57 C0 50 66 0F"),
        bytes.fromhex("C6 47 4C 00 E9 43 01 00 00"),
    ),
    (
        "startup profile sync state machine -> local continuation",
        0x0092B82A,
        bytes.fromhex("0F 84 8D 01 00 00"),
        bytes.fromhex("E9 8E 01 00 00 90"),
    ),
)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fmt(data: bytes) -> str:
    return " ".join(f"{x:02X}" for x in data)


def patch_one(
    data: bytearray,
    label: str,
    off: int,
    original: bytes,
    patched: bytes,
    changes: list[dict],
) -> None:
    if len(original) != len(patched):
        raise RuntimeError(f"{label}: patch length mismatch")

    current = bytes(data[off : off + len(original)])
    if current == patched:
        changes.append(
            {
                "label": label,
                "offset": f"0x{off:08X}",
                "status": "already-patched",
                "bytes": fmt(patched),
            }
        )
        return

    if current != original:
        raise RuntimeError(
            f"{label}: unexpected bytes at 0x{off:08X}: {fmt(current)}"
        )

    data[off : off + len(original)] = patched
    changes.append(
        {
            "label": label,
            "offset": f"0x{off:08X}",
            "status": "patched",
            "before": fmt(original),
            "after": fmt(patched),
        }
    )


def apply_bytes(data: bytearray) -> list[dict]:
    if bytes(data[ONLINE_OFF : ONLINE_OFF + len(ONLINE_FALSE)]) != ONLINE_FALSE:
        raise RuntimeError("Global IsOnline is not in Campaign offline/false state")

    changes: list[dict] = []

    for label, off, original, patched in PATCHES:
        patch_one(data, label, off, original, patched, changes)

    popup = bytes(data[POPUP_OFF : POPUP_OFF + len(POPUP_ORIG)])
    if popup == POPUP_ORIG:
        data[POPUP_OFF : POPUP_OFF + len(POPUP_SAFE)] = POPUP_SAFE
        changes.append(
            {
                "label": "obsolete sync/network popup wrapper -> local no-op",
                "offset": f"0x{POPUP_OFF:08X}",
                "status": "patched",
                "before": fmt(POPUP_ORIG),
                "after": fmt(POPUP_SAFE),
            }
        )
    elif popup == POPUP_SAFE:
        changes.append(
            {
                "label": "obsolete sync/network popup wrapper -> local no-op",
                "offset": f"0x{POPUP_OFF:08X}",
                "status": "already-patched",
                "bytes": fmt(POPUP_SAFE),
            }
        )
    else:
        raise RuntimeError(
            f"sync/network popup wrapper: unexpected bytes {fmt(popup)}"
        )

    patch_one(
        data,
        "GlobalSync submit -> built-in local completion SUCCESS=0",
        SYNC_SUBMIT_OFF,
        SYNC_SUBMIT_ORIG,
        SYNC_SUBMIT_LOCAL,
        changes,
    )

    return changes


def apply(root: Path) -> int:
    pkg = root / "_PACKAGE_PHASE5"
    ams = pkg / "AMS.exe"
    if not ams.is_file():
        raise FileNotFoundError(f"AMS.exe not found: {ams}")

    raw = ams.read_bytes()
    before = sha_bytes(raw)
    data = bytearray(raw)
    changes = apply_bytes(data)

    backup_dir = root / "_BACKUPS" / "CAMPAIGN-PROFILE-V1"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"AMS.exe.{before}.bak"
    if not backup.exists():
        shutil.copy2(ams, backup)

    tmp = ams.with_suffix(".profile-v1.tmp")
    tmp.write_bytes(data)

    verify = bytearray(tmp.read_bytes())
    if bytes(verify[ONLINE_OFF : ONLINE_OFF + len(ONLINE_FALSE)]) != ONLINE_FALSE:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("verification failed: Global IsOnline changed")

    for label, off, _original, patched in PATCHES:
        if bytes(verify[off : off + len(patched)]) != patched:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"verification failed: {label}")

    if bytes(verify[POPUP_OFF : POPUP_OFF + len(POPUP_SAFE)]) != POPUP_SAFE:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("verification failed: popup wrapper")

    if (
        bytes(verify[SYNC_SUBMIT_OFF : SYNC_SUBMIT_OFF + len(SYNC_SUBMIT_LOCAL)])
        != SYNC_SUBMIT_LOCAL
    ):
        tmp.unlink(missing_ok=True)
        raise RuntimeError("verification failed: GlobalSync local completion")

    tmp.replace(ams)

    after = sha_bytes(ams.read_bytes())
    report = {
        "phase": "Campaign Profile Adapter v1",
        "authority": "local Campaign profile / original UI observers only",
        "logical_connectivity": "offline/false",
        "remote_profile_validation": "retired",
        "profile_sync_loading_ui": "retired (3/3 known construction sites)",
        "global_sync_transport": "retired",
        "global_sync_completion": {
            "mode": "built-in original completion callback",
            "result_code": 0,
            "transport_started": False,
        },
        "popup_wrapper": "local no-op for obsolete sync/network popup",
        "sha256_before": before,
        "sha256_after": after,
        "backup": str(backup),
        "changes": changes,
    }

    trace = root / "_TRACE_MONTAR"
    trace.mkdir(parents=True, exist_ok=True)
    report_path = trace / "CAMPAIGN-PROFILE-V1.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("[OK] Campaign Profile Adapter v1 applied.")
    print("[PROFILE] remote/cloud sync retired; local completion active.")
    print("[PROFILE] STR_MENU_SYNC_LOADING sites neutralized: 3 / 3")
    print(f"[AMS] {after}")
    print(f"[REPORT] {report_path}")
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
