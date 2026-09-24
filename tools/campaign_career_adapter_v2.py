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

CAREER_BEGIN_MAGIC = 0xC0DEB072
RACE_FINISH_MAGIC = 0xC0DEF001

PRE_SITE_VA = 0x00A05690
PRE_SITE_OFF = 0x00604A90
PRE_SITE_ORIG = bytes.fromhex("55 8B EC 6A FF")

PRE_STUB_VA = 0x009DE120
PRE_STUB_OFF = 0x005DD520
PRE_STUB_ORIG = bytes.fromhex(
    "55 8B EC 6A FF 68 15 15 42 01 64 A1 00 00 00 00 "
    "50 83 EC 20 53 56 57 A1 00 7A 89 01 33 C5 50 8D "
    "45 F4 64 A3 00 00 00 00 C7 45 EC 00 00 00 00 8D "
    "4D D8 C6 45 F0 00 0F 57 C0 FF 75 F0 66 0F D6 45 "
    "D4 6A 00 C7 45 D4 00 00 00 00 E8 F1 D2 FE FF 8B "
    "7D D8 C7 45 FC"
)
PRE_SUCCESS_TRANSITION_VA = 0x00A1A540

POST_FACTORY_VA = 0x009DDFA0
POST_FACTORY_OFF = 0x005DD3A0
POST_FACTORY_ORIG = bytes.fromhex(
    "55 8B EC 6A FF 68 15 15 42 01 64 A1 00 00 00 00 50 83"
)

POST_NOTIFY_ECX_VA = 0x00A05650
POST_NOTIFY_ECX_OFF = 0x00604A50
POST_NOTIFY_ECX_ORIG = bytes.fromhex("8B 8B D0 00 00 00")
POST_NOTIFY_ECX_PATCH = bytes.fromhex("8B CB 90 90 90 90")

POST_NOTIFY_VA = 0x00D18890
POST_NOTIFY_OFF = 0x00917C90
POST_NOTIFY_ORIG = bytes.fromhex(
    "55 8B EC 6A FF 68 0A 19 43 01 64 A1 00 00 00 00 "
    "50 81 EC 94 00 00 00 A1 00 7A 89 01 33 C5 89 45 "
    "F0 56 57 50 8D 45 F4 64 A3 00 00 00 00 8B F9 89 "
    "7D 90 68 B8 AA 56 01 8D 45 D4 C7 45 D4 00 00 00 "
    "00 50 8D 4F 20 E8 D6 DA 78 FF 8D 4D A4 C7"
)

FINISH_SITE_VA = 0x00CC8828
FINISH_SITE_OFF = 0x008C7C28
FINISH_SITE_ORIG = bytes.fromhex("8B 75 EC C7 45 FC FF FF FF FF")
FINISH_RESUME_VA = 0x00CC8832
FINISH_CAVE_VA = 0x010E9BA5
FINISH_CAVE_OFF = 0x00CE8FA5
FINISH_CAVE_LEN = 43
CC_FINISH = b"\xCC" * FINISH_CAVE_LEN

V1_BEGIN_SITE_VA = 0x00C7E73B
V1_BEGIN_SITE_OFF = 0x0087DB3B
V1_BEGIN_SITE_ORIG = bytes.fromhex("8B C3 8B 4D F4")
V1_BEGIN_CAVE_VA = 0x01109DD5
V1_BEGIN_CAVE_OFF = 0x00D091D5
V1_BEGIN_CAVE_LEN = 43
CC_V1_BEGIN = b"\xCC" * V1_BEGIN_CAVE_LEN
RACE_BEGIN_MAGIC_V1 = 0xC0DEB001


def fmt(data: bytes) -> str:
    return " ".join(f"{x:02X}" for x in data)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel32(src_va: int, length: int, dst_va: int) -> bytes:
    delta = dst_va - (src_va + length)
    if not (-0x80000000 <= delta <= 0x7FFFFFFF):
        raise RuntimeError("rel32 out of range")
    return struct.pack("<i", delta)


def pic_iat_call(code: bytearray, base_va: int, selector: int) -> None:
    code += b"\x68" + struct.pack("<I", selector)
    call_va = base_va + len(code)
    code += b"\xE8\x00\x00\x00\x00"
    pop_va = call_va + 5
    code += b"\x58"
    code += b"\x05" + struct.pack("<I", (IGP_HTTPPOST_PREF_VA - pop_va) & 0xFFFFFFFF)
    code += b"\xFF\x10"


def build_pre_stub() -> bytes:
    code = bytearray()
    code += bytes.fromhex("55 8B EC 56 83 EC 08 8B F1")
    code += bytes.fromhex("8B 86 F8 00 00 00 89 04 24")
    code += bytes.fromhex("8B 86 FC 00 00 00 89 44 24 04")
    code += bytes.fromhex("8B CC")
    pic_iat_call(code, PRE_STUB_VA, CAREER_BEGIN_MAGIC)
    code += bytes.fromhex("85 C0")
    jz_index = len(code)
    code += b"\x74\x00"

    code += bytes.fromhex("C7 86 E0 00 00 00 00 00 00 00")
    code += bytes.fromhex("C7 86 E4 00 00 00 00 00 00 00")
    code += bytes.fromhex("8B CE")
    call_va = PRE_STUB_VA + len(code)
    code += b"\xE8" + rel32(call_va, 5, PRE_SUCCESS_TRANSITION_VA)

    fail_va = PRE_STUB_VA + len(code)
    code += bytes.fromhex("83 C4 08 5E 5D C3")

    next_va = PRE_STUB_VA + jz_index + 2
    delta = fail_va - next_va
    if not (-128 <= delta <= 127):
        raise RuntimeError("pre stub short branch out of range")
    code[jz_index + 1] = delta & 0xFF
    return bytes(code)


def build_post_factory_stub() -> bytes:
    return bytes.fromhex(
        "8B 44 24 04 "
        "C7 00 00 00 00 00 "
        "C7 40 04 00 00 00 00 "
        "C3"
    )


def build_post_notify_stub() -> bytes:
    code = bytearray()
    code += bytes.fromhex("53 56 57 8B F9")
    code += bytes.fromhex("83 7F 30 01")
    jne_index = len(code)
    code += b"\x75\x00"
    code += bytes.fromhex("C7 47 30 02 00 00 00")
    code += bytes.fromhex("C7 47 34 00 00 00 00")
    code += bytes.fromhex("C6 47 15 01 33 F6")

    loop_va = POST_NOTIFY_VA + len(code)
    code += bytes.fromhex("8B 47 0C 2B 47 08 C1 F8 02 3B F0")
    jae_index = len(code)
    code += b"\x73\x00"
    code += bytes.fromhex("8B 47 08 8B 1C B0 85 DB")
    jz_index = len(code)
    code += b"\x74\x00"
    code += bytes.fromhex("6A 00 8B 03 8B CB FF 50 24")

    next_va = POST_NOTIFY_VA + len(code)
    code += b"\x46"
    jmp_index = len(code)
    code += b"\xEB\x00"

    loop_done_va = POST_NOTIFY_VA + len(code)
    code += bytes.fromhex("C6 47 15 00 C6 47 14 00")
    done_va = POST_NOTIFY_VA + len(code)
    code += bytes.fromhex("5F 5E 5B C3")

    for index, target in (
        (jne_index, done_va),
        (jae_index, loop_done_va),
        (jz_index, next_va),
        (jmp_index, loop_va),
    ):
        next_ip = POST_NOTIFY_VA + index + 2
        delta = target - next_ip
        if not (-128 <= delta <= 127):
            raise RuntimeError("post notify short branch out of range")
        code[index + 1] = delta & 0xFF

    return bytes(code)


def pic_gateway_call(cave_va: int, prefix_len: int, selector: int) -> bytes:
    code = bytearray()
    code += b"\x68" + struct.pack("<I", selector)
    call_va = cave_va + prefix_len + len(code)
    code += b"\xE8\x00\x00\x00\x00"
    pop_va = call_va + 5
    code += b"\x58"
    code += b"\x05" + struct.pack("<I", (IGP_HTTPPOST_PREF_VA - pop_va) & 0xFFFFFFFF)
    code += b"\xFF\x10"
    return bytes(code)


def build_finish_stub() -> bytes:
    code = bytearray()
    code += b"\x9C\x60"
    code += b"\x8B\xCE"
    code += pic_gateway_call(FINISH_CAVE_VA, len(code), RACE_FINISH_MAGIC)
    code += b"\x61\x9D"
    code += FINISH_SITE_ORIG
    jmp_va = FINISH_CAVE_VA + len(code)
    code += b"\xE9" + rel32(jmp_va, 5, FINISH_RESUME_VA)
    if len(code) > FINISH_CAVE_LEN:
        raise RuntimeError("finish stub exceeds cave")
    return bytes(code) + b"\xCC" * (FINISH_CAVE_LEN - len(code))


def build_v1_begin_stub() -> bytes:
    code = bytearray()
    code += b"\x9C\x60"
    code += b"\x8B\xCB"
    code += pic_gateway_call(V1_BEGIN_CAVE_VA, len(code), RACE_BEGIN_MAGIC_V1)
    code += b"\x61\x9D"
    code += V1_BEGIN_SITE_ORIG
    code += b"\xC3"
    if len(code) > V1_BEGIN_CAVE_LEN:
        raise RuntimeError("v1 begin stub exceeds cave")
    return bytes(code) + b"\xCC" * (V1_BEGIN_CAVE_LEN - len(code))


PRE_STUB = build_pre_stub()
POST_FACTORY_STUB = build_post_factory_stub()
POST_NOTIFY_STUB = build_post_notify_stub()
PRE_SITE_PATCH = b"\xE9" + rel32(PRE_SITE_VA, 5, PRE_STUB_VA)

FINISH_STUB = build_finish_stub()
FINISH_SITE_PATCH = b"\xE9" + rel32(FINISH_SITE_VA, 5, FINISH_CAVE_VA) + b"\x90" * 5

V1_BEGIN_STUB = build_v1_begin_stub()
V1_BEGIN_SITE_PATCH = b"\xE8" + rel32(V1_BEGIN_SITE_VA, 5, V1_BEGIN_CAVE_VA)


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


def normalize_v1_begin(data: bytearray, changes: list[dict]) -> None:
    site = bytes(data[V1_BEGIN_SITE_OFF:V1_BEGIN_SITE_OFF+5])
    cave = bytes(data[V1_BEGIN_CAVE_OFF:V1_BEGIN_CAVE_OFF+V1_BEGIN_CAVE_LEN])

    if site == V1_BEGIN_SITE_ORIG and cave == CC_V1_BEGIN:
        return

    if site == V1_BEGIN_SITE_PATCH and cave == V1_BEGIN_STUB:
        data[V1_BEGIN_SITE_OFF:V1_BEGIN_SITE_OFF+5] = V1_BEGIN_SITE_ORIG
        data[V1_BEGIN_CAVE_OFF:V1_BEGIN_CAVE_OFF+V1_BEGIN_CAVE_LEN] = CC_V1_BEGIN
        changes.append({
            "label": "retire broad Race Adapter v1 BEGIN",
            "site": f"0x{V1_BEGIN_SITE_OFF:08X}",
        })
        return

    raise RuntimeError("Race Adapter v1 BEGIN is in an unknown partial state")


def install_finish(data: bytearray, changes: list[dict]) -> None:
    site = bytes(data[FINISH_SITE_OFF:FINISH_SITE_OFF+10])
    cave = bytes(data[FINISH_CAVE_OFF:FINISH_CAVE_OFF+FINISH_CAVE_LEN])

    if site == FINISH_SITE_PATCH and cave == FINISH_STUB:
        return

    if site != FINISH_SITE_ORIG or cave != CC_FINISH:
        raise RuntimeError("FINISH metric adapter is in an unknown state")

    data[FINISH_CAVE_OFF:FINISH_CAVE_OFF+FINISH_CAVE_LEN] = FINISH_STUB
    data[FINISH_SITE_OFF:FINISH_SITE_OFF+10] = FINISH_SITE_PATCH
    changes.append({
        "label": "install Campaign metric FINISH adapter",
        "site": f"0x{FINISH_SITE_OFF:08X}",
        "cave": f"0x{FINISH_CAVE_OFF:08X}",
    })


def apply(root: Path) -> int:
    package = root / "_PACKAGE_PHASE5"
    ams = package / "AMS.exe"
    core = root / "prebuilt" / "campaign-core" / "IGPLib_x86.dll"
    target_core = package / "IGPLib_x86.dll"
    events = package / "CampaignEvents.dat"
    objectives = package / "CampaignObjectives.dat"

    for required in (ams, core, events, objectives):
        if not required.is_file():
            raise FileNotFoundError(f"required file missing: {required}")

    data = bytearray(ams.read_bytes())
    validate_pe32_x86(data)

    already = (
        bytes(data[PRE_SITE_OFF:PRE_SITE_OFF+5]) == PRE_SITE_PATCH
        and bytes(data[PRE_STUB_OFF:PRE_STUB_OFF+len(PRE_STUB)]) == PRE_STUB
        and bytes(data[POST_FACTORY_OFF:POST_FACTORY_OFF+len(POST_FACTORY_STUB)]) == POST_FACTORY_STUB
        and bytes(data[POST_NOTIFY_ECX_OFF:POST_NOTIFY_ECX_OFF+6]) == POST_NOTIFY_ECX_PATCH
        and bytes(data[POST_NOTIFY_OFF:POST_NOTIFY_OFF+len(POST_NOTIFY_STUB)]) == POST_NOTIFY_STUB
        and bytes(data[FINISH_SITE_OFF:FINISH_SITE_OFF+10]) == FINISH_SITE_PATCH
        and bytes(data[FINISH_CAVE_OFF:FINISH_CAVE_OFF+FINISH_CAVE_LEN]) == FINISH_STUB
    )
    if already:
        shutil.copy2(core, target_core)
        print("[OK] Campaign Career Adapter v2 already active; Core refreshed.")
        return 0

    require(data, PRE_SITE_OFF, PRE_SITE_ORIG, "CareerServer pre entry")
    require(data, PRE_STUB_OFF, PRE_STUB_ORIG, "PreCareerEventRequest factory")
    require(data, POST_FACTORY_OFF, POST_FACTORY_ORIG, "PostCareerEventRequest factory")
    require(data, POST_NOTIFY_ECX_OFF, POST_NOTIFY_ECX_ORIG, "CareerServer post notifier callsite")
    require(data, POST_NOTIFY_OFF, POST_NOTIFY_ORIG, "PostCareerEventRequest serializer")

    changes: list[dict] = []
    normalize_v1_begin(data, changes)
    install_finish(data, changes)

    before = sha256_bytes(data)
    backup_dir = root / "_BACKUPS" / "CAMPAIGN-CAREER-ADAPTER-V2"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"AMS.{before}.bak"
    if not backup.exists():
        shutil.copy2(ams, backup)

    data[PRE_STUB_OFF:PRE_STUB_OFF+len(PRE_STUB)] = PRE_STUB
    data[PRE_SITE_OFF:PRE_SITE_OFF+5] = PRE_SITE_PATCH
    data[POST_FACTORY_OFF:POST_FACTORY_OFF+len(POST_FACTORY_STUB)] = POST_FACTORY_STUB
    data[POST_NOTIFY_ECX_OFF:POST_NOTIFY_ECX_OFF+6] = POST_NOTIFY_ECX_PATCH
    data[POST_NOTIFY_OFF:POST_NOTIFY_OFF+len(POST_NOTIFY_STUB)] = POST_NOTIFY_STUB

    changes += [
        {
            "label": "CareerServer PRE -> CampaignBeginRaceAdapter",
            "site_va": f"0x{PRE_SITE_VA:08X}",
            "stub_va": f"0x{PRE_STUB_VA:08X}",
        },
        {
            "label": "retire PostCareerEventRequest construction",
            "factory_va": f"0x{POST_FACTORY_VA:08X}",
        },
        {
            "label": "Post serializer -> local CareerServer completion notification",
            "notifier_va": f"0x{POST_NOTIFY_VA:08X}",
        },
    ]

    tmp = ams.with_suffix(".career-v2.tmp")
    tmp.write_bytes(data)
    verify = tmp.read_bytes()

    require(verify, PRE_SITE_OFF, PRE_SITE_PATCH, "PRE redirect verification")
    require(verify, PRE_STUB_OFF, PRE_STUB, "PRE stub verification")
    require(verify, POST_FACTORY_OFF, POST_FACTORY_STUB, "POST factory verification")
    require(verify, POST_NOTIFY_ECX_OFF, POST_NOTIFY_ECX_PATCH, "POST ECX verification")
    require(verify, POST_NOTIFY_OFF, POST_NOTIFY_STUB, "POST notifier verification")
    require(verify, FINISH_SITE_OFF, FINISH_SITE_PATCH, "FINISH verification")
    require(verify, FINISH_CAVE_OFF, FINISH_STUB, "FINISH cave verification")

    tmp.replace(ams)
    shutil.copy2(core, target_core)

    report_dir = root / "_TRACE_MONTAR"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / "CAMPAIGN-CAREER-ADAPTER-V2.json"
    payload = {
        "phase": "Campaign Career Adapter v2",
        "authority": {
            "pre_career_request": "retired",
            "post_career_request": "retired",
            "remote_race_token": "retired / zeroed",
            "event_progression": "Campaign Core",
            "objectives": "CampaignObjectives.dat",
            "rewards": "CampaignEvents.dat",
        },
        "verified_fields": {
            "CareerServer+0xF8": "event_id",
            "CareerServer+0xFC": "car_id",
            "source": "PreCareerEventRequest serializer field names",
        },
        "finish_metrics": "read-only engine metrics -> CampaignObjectiveEvaluate",
        "old_post_parser_authoritative": False,
        "aslr_safe": True,
        "iat_rva": f"0x{IGP_HTTPPOST_IAT_RVA:08X}",
        "sha256_before": before,
        "sha256_after": sha256(ams),
        "core_sha256": sha256(target_core),
        "backup": str(backup),
        "changes": changes,
    }
    report.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[OK] Campaign Career Adapter v2 applied.")
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
