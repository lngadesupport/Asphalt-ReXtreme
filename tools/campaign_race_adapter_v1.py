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

RACE_BEGIN_MAGIC = 0xC0DEB001
RACE_FINISH_MAGIC = 0xC0DEF001

BEGIN_SITE_VA = 0x00C7E73B
BEGIN_SITE_OFF = 0x0087DB3B
BEGIN_SITE_ORIG = bytes.fromhex("8B C3 8B 4D F4")

FINISH_SITE_VA = 0x00CC8828
FINISH_SITE_OFF = 0x008C7C28
FINISH_SITE_ORIG = bytes.fromhex("8B 75 EC C7 45 FC FF FF FF FF")
FINISH_RESUME_VA = 0x00CC8832

BEGIN_CAVE_VA = 0x01109DD5
BEGIN_CAVE_OFF = 0x00D091D5
BEGIN_CAVE_LEN = 43

FINISH_CAVE_VA = 0x010E9BA5
FINISH_CAVE_OFF = 0x00CE8FA5
FINISH_CAVE_LEN = 43

CC_BEGIN = b"\xCC" * BEGIN_CAVE_LEN
CC_FINISH = b"\xCC" * FINISH_CAVE_LEN


def fmt(data: bytes) -> str:
    return " ".join(f"{x:02X}" for x in data)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel32(src_va: int, length: int, dst_va: int) -> bytes:
    delta = dst_va - (src_va + length)
    if not (-0x80000000 <= delta <= 0x7FFFFFFF):
        raise RuntimeError("rel32 out of range")
    return struct.pack("<i", delta)


def pic_gateway_call(cave_va: int, prefix_len: int, selector: int) -> bytes:
    code = bytearray()
    code += b"\x68" + struct.pack("<I", selector)
    code += b"\xE8\x00\x00\x00\x00"
    code += b"\x58"
    pop_next = cave_va + prefix_len + len(code)
    code += b"\x05" + struct.pack("<I", (IGP_HTTPPOST_PREF_VA - pop_next) & 0xFFFFFFFF)
    code += b"\xFF\x10"
    return bytes(code)


def build_begin_stub() -> bytes:
    code = bytearray()
    code += b"\x9C\x60"          # pushfd / pushad
    code += b"\x8B\xCB"          # mov ecx,ebx ; GameModeGUIBase*
    code += pic_gateway_call(BEGIN_CAVE_VA, len(code), RACE_BEGIN_MAGIC)
    code += b"\x61\x9D"          # popad / popfd
    code += BEGIN_SITE_ORIG         # original: mov eax,ebx / mov ecx,[ebp-0C]
    code += b"\xC3"                # return to BEGIN_SITE+5
    if len(code) > BEGIN_CAVE_LEN:
        raise RuntimeError("begin stub exceeds cave")
    return bytes(code) + b"\xCC" * (BEGIN_CAVE_LEN - len(code))


def build_finish_stub() -> bytes:
    code = bytearray()
    code += b"\x9C\x60"          # pushfd / pushad
    code += b"\x8B\xCE"          # mov ecx,esi ; GameModeGUIBase*
    code += pic_gateway_call(FINISH_CAVE_VA, len(code), RACE_FINISH_MAGIC)
    code += b"\x61\x9D"          # popad / popfd
    code += FINISH_SITE_ORIG        # two original instructions
    jmp_va = FINISH_CAVE_VA + len(code)
    code += b"\xE9" + rel32(jmp_va, 5, FINISH_RESUME_VA)
    if len(code) > FINISH_CAVE_LEN:
        raise RuntimeError("finish stub exceeds cave")
    return bytes(code) + b"\xCC" * (FINISH_CAVE_LEN - len(code))


BEGIN_STUB = build_begin_stub()
FINISH_STUB = build_finish_stub()
BEGIN_SITE_PATCH = b"\xE8" + rel32(BEGIN_SITE_VA, 5, BEGIN_CAVE_VA)
FINISH_SITE_PATCH = b"\xE9" + rel32(FINISH_SITE_VA, 5, FINISH_CAVE_VA) + b"\x90" * 5


def validate_pe32_x86(data: bytes) -> None:
    if data[:2] != b"MZ":
        raise RuntimeError("AMS.exe is not MZ")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe+4] != b"PE\0\0":
        raise RuntimeError("invalid PE signature")
    if struct.unpack_from("<H", data, pe + 4)[0] != 0x014C:
        raise RuntimeError("expected x86 image")
    opt = pe + 24
    if struct.unpack_from("<H", data, opt)[0] != 0x010B:
        raise RuntimeError("expected PE32")
    if struct.unpack_from("<I", data, opt + 28)[0] != IMAGE_BASE:
        raise RuntimeError("unexpected preferred image base")


def require(data: bytes, off: int, expected: bytes, name: str) -> None:
    current = bytes(data[off:off+len(expected)])
    if current != expected:
        raise RuntimeError(
            f"{name}: unexpected bytes at 0x{off:08X}: "
            f"[{fmt(current)}], expected [{fmt(expected)}]"
        )


def apply(root: Path) -> int:
    package = root / "_PACKAGE_PHASE5"
    ams = package / "AMS.exe"
    target_core = package / "IGPLib_x86.dll"
    prebuilt_core = root / "prebuilt" / "campaign-core" / "IGPLib_x86.dll"
    events = package / "CampaignEvents.dat"
    objectives = package / "CampaignObjectives.dat"

    for required in (ams, prebuilt_core, events, objectives):
        if not required.is_file():
            raise FileNotFoundError(f"required file missing: {required}")

    data = bytearray(ams.read_bytes())
    validate_pe32_x86(data)

    begin_site = bytes(data[BEGIN_SITE_OFF:BEGIN_SITE_OFF+5])
    finish_site = bytes(data[FINISH_SITE_OFF:FINISH_SITE_OFF+10])
    begin_cave = bytes(data[BEGIN_CAVE_OFF:BEGIN_CAVE_OFF+BEGIN_CAVE_LEN])
    finish_cave = bytes(data[FINISH_CAVE_OFF:FINISH_CAVE_OFF+FINISH_CAVE_LEN])

    already = (
        begin_site == BEGIN_SITE_PATCH
        and finish_site == FINISH_SITE_PATCH
        and begin_cave == BEGIN_STUB
        and finish_cave == FINISH_STUB
    )

    if already:
        shutil.copy2(prebuilt_core, target_core)
        print("[OK] Campaign Race Adapter v1 already active; Core refreshed.")
        return 0

    require(data, BEGIN_SITE_OFF, BEGIN_SITE_ORIG, "GameModeGUIBase constructor tail")
    require(data, FINISH_SITE_OFF, FINISH_SITE_ORIG, "result-screen creation tail")
    require(data, BEGIN_CAVE_OFF, CC_BEGIN, "BEGIN code cave")
    require(data, FINISH_CAVE_OFF, CC_FINISH, "FINISH code cave")

    before = hashlib.sha256(data).hexdigest()

    backup_dir = root / "_BACKUPS" / "CAMPAIGN-RACE-ADAPTER-V1"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"AMS.{before}.bak"
    if not backup.exists():
        shutil.copy2(ams, backup)

    # Install stub bodies first, then redirect execution.
    data[BEGIN_CAVE_OFF:BEGIN_CAVE_OFF+BEGIN_CAVE_LEN] = BEGIN_STUB
    data[FINISH_CAVE_OFF:FINISH_CAVE_OFF+FINISH_CAVE_LEN] = FINISH_STUB
    data[BEGIN_SITE_OFF:BEGIN_SITE_OFF+5] = BEGIN_SITE_PATCH
    data[FINISH_SITE_OFF:FINISH_SITE_OFF+10] = FINISH_SITE_PATCH

    tmp = ams.with_suffix(".race-adapter.tmp")
    tmp.write_bytes(data)

    verify = tmp.read_bytes()
    require(verify, BEGIN_SITE_OFF, BEGIN_SITE_PATCH, "BEGIN redirect verification")
    require(verify, FINISH_SITE_OFF, FINISH_SITE_PATCH, "FINISH redirect verification")
    require(verify, BEGIN_CAVE_OFF, BEGIN_STUB, "BEGIN stub verification")
    require(verify, FINISH_CAVE_OFF, FINISH_STUB, "FINISH stub verification")

    tmp.replace(ams)
    shutil.copy2(prebuilt_core, target_core)

    report_dir = root / "_TRACE_MONTAR"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / "CAMPAIGN-RACE-ADAPTER-V1.json"

    payload = {
        "phase": "Campaign Race Adapter v1",
        "begin": {
            "site_va": f"0x{BEGIN_SITE_VA:08X}",
            "site_file_offset": f"0x{BEGIN_SITE_OFF:08X}",
            "cave_va": f"0x{BEGIN_CAVE_VA:08X}",
            "selector": f"0x{RACE_BEGIN_MAGIC:08X}",
            "semantic": "GameModeGUIBase construction -> CampaignBeginRaceFromGui",
        },
        "finish": {
            "site_va": f"0x{FINISH_SITE_VA:08X}",
            "site_file_offset": f"0x{FINISH_SITE_OFF:08X}",
            "cave_va": f"0x{FINISH_CAVE_VA:08X}",
            "selector": f"0x{RACE_FINISH_MAGIC:08X}",
            "semantic": "result screen creation -> CampaignFinishRaceFromGui",
        },
        "aslr_safe": True,
        "iat_rva": f"0x{IGP_HTTPPOST_IAT_RVA:08X}",
        "requires": [
            "CampaignEvents.dat",
            "CampaignObjectives.dat",
            "Campaign Core with race adapters",
        ],
        "legacy_result_sync_authoritative": False,
        "sha256_before": before,
        "sha256_after": sha256(ams),
        "core_sha256": sha256(target_core),
        "backup": str(backup),
    }
    report.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[OK] Campaign Race Adapter v1 applied.")
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
