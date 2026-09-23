#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

FILE_OFFSET = 0x00686DA4
STATIC_VA = 0x00A879A4
TARGET_VA = 0x00A87B88
ORIGINAL = bytes.fromhex("0F 85 DE 01 00 00")   # jne 0x00A87B88
PATCHED  = bytes.fromhex("E9 DF 01 00 00 90")   # jmp 0x00A87B88 ; nop

PHASE36_OFFSET = 0x009168B0
PHASE36_EXPECTED = bytes.fromhex("31 C0 C2 18 00")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fmt(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


def load_exe(root: Path):
    exe = root / "_PACKAGE_PHASE5" / "AMS.exe"
    if not exe.is_file():
        raise FileNotFoundError(f"AMS.exe nao encontrado: {exe}")
    data = bytearray(exe.read_bytes())
    return exe, data


def status_for(cur: bytes) -> str:
    if cur == ORIGINAL:
        return "ORIGINAL_BRANCH"
    if cur == PATCHED:
        return "R15_PATCHED"
    return "UNKNOWN_BYTES"


def write_report(root: Path, report: dict):
    out = root / "_TRACE_MONTAR"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "R15-BUILDCAR-OFFLINE-BRIDGE.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def base_report(exe: Path, data: bytearray):
    cur = bytes(data[FILE_OFFSET:FILE_OFFSET + len(ORIGINAL)])
    phase36 = bytes(data[PHASE36_OFFSET:PHASE36_OFFSET + len(PHASE36_EXPECTED)])
    return {
        "name": "R15 BuildCar Offline Bridge",
        "created_at": datetime.now().isoformat(),
        "exe": str(exe),
        "sha256_before": sha256_bytes(data),
        "static_va": f"0x{STATIC_VA:08X}",
        "target_va": f"0x{TARGET_VA:08X}",
        "file_offset": f"0x{FILE_OFFSET:08X}",
        "expected_original": fmt(ORIGINAL),
        "patched": fmt(PATCHED),
        "current": fmt(cur),
        "status_before": status_for(cur),
        "phase36_current": fmt(phase36),
        "phase36_expected_campaign_stub": fmt(PHASE36_EXPECTED),
        "phase36_stub_present": phase36 == PHASE36_EXPECTED,
        "semantics": {
            "before": "JNE online_path: follows online BuildCar path only when GlobalIsOnline returned non-zero",
            "after": "JMP online_path: forces only GS_Garage::BuildCar into the existing online/craft path",
            "global_connectivity": "unchanged",
            "aslr_safe": True,
            "patch_size": 6,
        },
    }


def do_plan(root: Path) -> int:
    exe, data = load_exe(root)
    report = base_report(exe, data)
    report["action"] = "plan"
    report["can_apply"] = report["status_before"] in ("ORIGINAL_BRANCH", "R15_PATCHED")
    if report["status_before"] == "UNKNOWN_BYTES":
        report["error"] = "Target bytes are neither original nor known R15 bytes; refusing to patch."
    path = write_report(root, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n[REPORT] {path}")
    return 0 if report["can_apply"] else 4


def do_apply(root: Path) -> int:
    exe, data = load_exe(root)
    report = base_report(exe, data)
    report["action"] = "apply"

    cur = bytes(data[FILE_OFFSET:FILE_OFFSET + len(ORIGINAL)])
    if cur == PATCHED:
        report["result"] = "already_applied"
        report["sha256_after"] = report["sha256_before"]
        path = write_report(root, report)
        print("[OK] R15 ja esta aplicada.")
        print(f"[REPORT] {path}")
        return 0

    if cur != ORIGINAL:
        report["result"] = "refused_unknown_bytes"
        report["error"] = "Target bytes differ from expected original bytes."
        path = write_report(root, report)
        print("[ERRO] Bytes inesperados no ponto R15; nada foi alterado.")
        print(f"[ATUAL] {fmt(cur)}")
        print(f"[ESPERADO] {fmt(ORIGINAL)}")
        print(f"[REPORT] {path}")
        return 5

    backups = root / "_BACKUPS" / "R15"
    backups.mkdir(parents=True, exist_ok=True)
    backup = backups / f"AMS.exe.{report['sha256_before']}.bak"
    if not backup.exists():
        shutil.copy2(exe, backup)

    data[FILE_OFFSET:FILE_OFFSET + len(PATCHED)] = PATCHED
    exe.write_bytes(data)

    verify = exe.read_bytes()
    got = verify[FILE_OFFSET:FILE_OFFSET + len(PATCHED)]
    if got != PATCHED:
        shutil.copy2(backup, exe)
        raise RuntimeError("Verification failed; backup restored.")

    report["backup"] = str(backup)
    report["result"] = "applied"
    report["sha256_after"] = sha256_bytes(verify)
    report["status_after"] = "R15_PATCHED"
    path = write_report(root, report)

    print("[OK] R15 aplicada.")
    print(f"[OFFSET] 0x{FILE_OFFSET:08X}")
    print(f"[ANTES ] {fmt(ORIGINAL)}")
    print(f"[DEPOIS] {fmt(PATCHED)}")
    print(f"[SHA256] {report['sha256_after']}")
    print(f"[BACKUP] {backup}")
    print(f"[REPORT] {path}")
    return 0


def do_revert(root: Path) -> int:
    exe, data = load_exe(root)
    report = base_report(exe, data)
    report["action"] = "revert"

    cur = bytes(data[FILE_OFFSET:FILE_OFFSET + len(ORIGINAL)])
    if cur == ORIGINAL:
        report["result"] = "already_reverted"
        report["sha256_after"] = report["sha256_before"]
        path = write_report(root, report)
        print("[OK] R15 ja esta revertida.")
        print(f"[REPORT] {path}")
        return 0

    if cur != PATCHED:
        report["result"] = "refused_unknown_bytes"
        report["error"] = "Target bytes differ from expected R15 bytes."
        path = write_report(root, report)
        print("[ERRO] Bytes inesperados; revert cirurgico recusado.")
        print(f"[ATUAL] {fmt(cur)}")
        print(f"[R15  ] {fmt(PATCHED)}")
        print(f"[REPORT] {path}")
        return 6

    backups = root / "_BACKUPS" / "R15"
    backups.mkdir(parents=True, exist_ok=True)
    pre = backups / f"AMS.exe.pre-revert.{report['sha256_before']}.bak"
    if not pre.exists():
        shutil.copy2(exe, pre)

    data[FILE_OFFSET:FILE_OFFSET + len(ORIGINAL)] = ORIGINAL
    exe.write_bytes(data)
    verify = exe.read_bytes()
    got = verify[FILE_OFFSET:FILE_OFFSET + len(ORIGINAL)]
    if got != ORIGINAL:
        shutil.copy2(pre, exe)
        raise RuntimeError("Revert verification failed; pre-revert backup restored.")

    report["pre_revert_backup"] = str(pre)
    report["result"] = "reverted"
    report["sha256_after"] = sha256_bytes(verify)
    report["status_after"] = "ORIGINAL_BRANCH"
    path = write_report(root, report)

    print("[OK] R15 revertida.")
    print(f"[OFFSET] 0x{FILE_OFFSET:08X}")
    print(f"[RESTAURADO] {fmt(ORIGINAL)}")
    print(f"[SHA256] {report['sha256_after']}")
    print(f"[REPORT] {path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--revert", action="store_true")
    ns = ap.parse_args()
    root = Path(ns.project_root).resolve()

    try:
        if ns.plan:
            return do_plan(root)
        if ns.apply:
            return do_apply(root)
        return do_revert(root)
    except Exception as e:
        print(f"[ERRO] {e}")
        return 10


if __name__ == "__main__":
    raise SystemExit(main())
