#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path

import campaign_career_adapter_v2 as v2

IMAGE_BASE = v2.IMAGE_BASE
IGP_HTTPPOST_IAT_RVA = v2.IGP_HTTPPOST_IAT_RVA
IGP_HTTPPOST_PREF_VA = v2.IGP_HTTPPOST_PREF_VA

POST_MAGIC = 0xC0DECA73

POST_CALL_VA = 0x00A05650
POST_CALL_OFF = 0x00604A50
POST_RESUME_VA = 0x00A0565B
POST_CALL_LEN = 11

# v2 used this cave for a broad end-race metrics adapter. v3 reuses it for
# a narrower PostCareerEventRequest bridge.
BRIDGE_VA = v2.FINISH_CAVE_VA
BRIDGE_OFF = v2.FINISH_CAVE_OFF
BRIDGE_LEN = v2.FINISH_CAVE_LEN


def rel32(src_va: int, insn_len: int, dst_va: int) -> bytes:
    delta = dst_va - (src_va + insn_len)
    if not (-0x80000000 <= delta <= 0x7FFFFFFF):
        raise RuntimeError("rel32 out of range")
    return struct.pack("<i", delta)


def build_original_post_call() -> bytes:
    return (
        v2.POST_NOTIFY_ECX_ORIG
        + b"\xE8"
        + rel32(POST_CALL_VA + len(v2.POST_NOTIFY_ECX_ORIG), 5, v2.POST_NOTIFY_VA)
    )


def build_v2_post_call() -> bytes:
    return (
        v2.POST_NOTIFY_ECX_PATCH
        + b"\xE8"
        + rel32(POST_CALL_VA + len(v2.POST_NOTIFY_ECX_PATCH), 5, v2.POST_NOTIFY_VA)
    )


def pic_iat_call(code: bytearray, base_va: int, selector: int) -> None:
    code += b"\x68" + struct.pack("<I", selector)
    call_va = base_va + len(code)
    code += b"\xE8\x00\x00\x00\x00"
    pop_va = call_va + 5
    code += b"\x58"
    code += b"\x05" + struct.pack(
        "<I", (IGP_HTTPPOST_PREF_VA - pop_va) & 0xFFFFFFFF
    )
    code += b"\xFF\x10"


def build_bridge() -> bytes:
    code = bytearray()

    # EBX is CareerServer. +0xD0 is the fully populated local
    # PostCareerEventRequest shared object.
    code += bytes.fromhex("8B 8B D0 00 00 00")
    pic_iat_call(code, BRIDGE_VA, POST_MAGIC)
    code += bytes.fromhex("85 C0")
    jz = len(code)
    code += bytes.fromhex("74 00")

    # Campaign commit succeeded: notify only the preserved visual observers.
    code += bytes.fromhex("8B CB")
    call_va = BRIDGE_VA + len(code)
    code += b"\xE8" + rel32(call_va, 5, v2.POST_NOTIFY_VA)

    resume = len(code)
    jmp_va = BRIDGE_VA + len(code)
    code += b"\xE9" + rel32(jmp_va, 5, POST_RESUME_VA)

    next_ip = BRIDGE_VA + jz + 2
    delta = (BRIDGE_VA + resume) - next_ip
    if not (-128 <= delta <= 127):
        raise RuntimeError("bridge short jump out of range")
    code[jz + 1] = delta & 0xFF

    if len(code) > BRIDGE_LEN:
        raise RuntimeError(f"career v3 bridge too large: {len(code)} > {BRIDGE_LEN}")
    return bytes(code) + b"\xCC" * (BRIDGE_LEN - len(code))


POST_CALL_ORIG = build_original_post_call()
POST_CALL_V2 = build_v2_post_call()
POST_CALL_V3 = b"\xE9" + rel32(POST_CALL_VA, 5, BRIDGE_VA) + b"\x90" * 6
BRIDGE = build_bridge()


def bytes_at(data: bytes, off: int, n: int) -> bytes:
    return bytes(data[off:off+n])


def require_one(data: bytes, off: int, states: tuple[bytes, ...], label: str) -> bytes:
    n = len(states[0])
    if any(len(x) != n for x in states):
        raise RuntimeError(f"{label}: internal state lengths differ")
    current = bytes_at(data, off, n)
    if current not in states:
        raise RuntimeError(
            f"{label}: unknown bytes at 0x{off:08X}: "
            + " ".join(f"{b:02X}" for b in current)
        )
    return current


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply(root: Path) -> int:
    pkg = root / "_PACKAGE_PHASE5"
    ams = pkg / "AMS.exe"
    core = root / "prebuilt" / "campaign-core" / "IGPLib_x86.dll"
    target_core = pkg / "IGPLib_x86.dll"
    events = pkg / "CampaignEvents.dat"

    for p in (ams, core, events):
        if not p.is_file():
            raise FileNotFoundError(f"required file missing: {p}")

    data = bytearray(ams.read_bytes())
    v2.validate_pe32_x86(data)

    # Fully idempotent v3 state.
    already = (
        bytes_at(data, v2.PRE_SITE_OFF, 5) == v2.PRE_SITE_PATCH
        and bytes_at(data, v2.PRE_STUB_OFF, len(v2.PRE_STUB)) == v2.PRE_STUB
        and bytes_at(data, v2.POST_FACTORY_OFF, len(v2.POST_FACTORY_ORIG)) == v2.POST_FACTORY_ORIG
        and bytes_at(data, POST_CALL_OFF, POST_CALL_LEN) == POST_CALL_V3
        and bytes_at(data, v2.POST_NOTIFY_OFF, len(v2.POST_NOTIFY_STUB)) == v2.POST_NOTIFY_STUB
        and bytes_at(data, v2.FINISH_SITE_OFF, len(v2.FINISH_SITE_ORIG)) == v2.FINISH_SITE_ORIG
        and bytes_at(data, BRIDGE_OFF, BRIDGE_LEN) == BRIDGE
    )
    if already:
        shutil.copy2(core, target_core)
        print("[OK] Campaign Career Adapter v3 already active; Core refreshed.")
        return 0

    changes = []

    # PRE can be vanilla or already v2/v3.
    pre_site = require_one(
        data, v2.PRE_SITE_OFF,
        (v2.PRE_SITE_ORIG, v2.PRE_SITE_PATCH),
        "Career PRE entry",
    )
    pre_stub = require_one(
        data, v2.PRE_STUB_OFF,
        (v2.PRE_STUB_ORIG, v2.PRE_STUB),
        "Career PRE stub",
    )
    if pre_site == v2.PRE_SITE_ORIG and pre_stub != v2.PRE_STUB_ORIG:
        raise RuntimeError("Career PRE partial state")
    if pre_site == v2.PRE_SITE_PATCH and pre_stub != v2.PRE_STUB:
        raise RuntimeError("Career PRE partial state")

    # v2 deliberately nulled the POST factory. v3 restores it so the game can
    # build the result object containing star1/star2/star3/position/race_time.
    factory = require_one(
        data, v2.POST_FACTORY_OFF,
        (v2.POST_FACTORY_ORIG, v2.POST_FACTORY_STUB),
        "PostCareerEventRequest factory",
    )

    post_call = require_one(
        data, POST_CALL_OFF,
        (POST_CALL_ORIG, POST_CALL_V2, POST_CALL_V3),
        "Career POST callsite",
    )

    notifier = require_one(
        data, v2.POST_NOTIFY_OFF,
        (v2.POST_NOTIFY_ORIG, v2.POST_NOTIFY_STUB),
        "Career visual notifier",
    )

    finish_site = require_one(
        data, v2.FINISH_SITE_OFF,
        (v2.FINISH_SITE_ORIG, v2.FINISH_SITE_PATCH),
        "broad FINISH adapter site",
    )
    cave = require_one(
        data, BRIDGE_OFF,
        (v2.CC_FINISH, v2.FINISH_STUB, BRIDGE),
        "career bridge cave",
    )

    # Normalize the older broad BEGIN patch if present.
    v2.normalize_v1_begin(data, changes)

    before = hashlib.sha256(data).hexdigest()
    backup_dir = root / "_BACKUPS" / "CAMPAIGN-CAREER-ADAPTER-V3"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"AMS.{before}.bak"
    if not backup.exists():
        shutil.copy2(ams, backup)

    if pre_site == v2.PRE_SITE_ORIG:
        data[v2.PRE_STUB_OFF:v2.PRE_STUB_OFF+len(v2.PRE_STUB)] = v2.PRE_STUB
        data[v2.PRE_SITE_OFF:v2.PRE_SITE_OFF+5] = v2.PRE_SITE_PATCH
        changes.append({"label": "Career PRE -> local Campaign session"})

    if factory == v2.POST_FACTORY_STUB:
        data[v2.POST_FACTORY_OFF:v2.POST_FACTORY_OFF+len(v2.POST_FACTORY_ORIG)] = v2.POST_FACTORY_ORIG
        changes.append({"label": "restore POST result-object construction only"})

    # Retire v2 broad metric interception. v3 obtains the three star results
    # from the fully populated PostCareerEventRequest instead.
    if finish_site == v2.FINISH_SITE_PATCH:
        if cave != v2.FINISH_STUB:
            raise RuntimeError("v2 FINISH site active but cave differs")
        data[v2.FINISH_SITE_OFF:v2.FINISH_SITE_OFF+len(v2.FINISH_SITE_ORIG)] = v2.FINISH_SITE_ORIG
        changes.append({"label": "retire broad objective-metric FINISH hook"})

    # Install visual-only notifier if still vanilla.
    if notifier == v2.POST_NOTIFY_ORIG:
        data[v2.POST_NOTIFY_OFF:v2.POST_NOTIFY_OFF+len(v2.POST_NOTIFY_STUB)] = v2.POST_NOTIFY_STUB
        changes.append({"label": "install local CareerServer visual notifier"})

    data[BRIDGE_OFF:BRIDGE_OFF+BRIDGE_LEN] = BRIDGE
    data[POST_CALL_OFF:POST_CALL_OFF+POST_CALL_LEN] = POST_CALL_V3
    changes.append({
        "label": "PostCareer result object -> Campaign Core -> visual notifier",
        "selector": "0xC0DECA73",
    })

    tmp = ams.with_suffix(".career-v3.tmp")
    tmp.write_bytes(data)
    verify = tmp.read_bytes()

    if bytes_at(verify, v2.PRE_SITE_OFF, 5) != v2.PRE_SITE_PATCH:
        raise RuntimeError("PRE verification failed")
    if bytes_at(verify, v2.POST_FACTORY_OFF, len(v2.POST_FACTORY_ORIG)) != v2.POST_FACTORY_ORIG:
        raise RuntimeError("POST factory verification failed")
    if bytes_at(verify, POST_CALL_OFF, POST_CALL_LEN) != POST_CALL_V3:
        raise RuntimeError("POST bridge callsite verification failed")
    if bytes_at(verify, BRIDGE_OFF, BRIDGE_LEN) != BRIDGE:
        raise RuntimeError("POST bridge cave verification failed")
    if bytes_at(verify, v2.FINISH_SITE_OFF, len(v2.FINISH_SITE_ORIG)) != v2.FINISH_SITE_ORIG:
        raise RuntimeError("old FINISH hook was not retired")

    tmp.replace(ams)
    shutil.copy2(core, target_core)

    trace = root / "_TRACE_MONTAR"
    trace.mkdir(parents=True, exist_ok=True)
    report = trace / "CAMPAIGN-CAREER-ADAPTER-V3.json"
    payload = {
        "phase": "Campaign Career Adapter v3",
        "authority": {
            "race_simulation": "original preserved engine",
            "star_result_source": "read-only PostCareerEventRequest star1/star2/star3",
            "position_time_source": "read-only PostCareerEventRequest",
            "rewards": "Campaign Core / CampaignEvents.dat",
            "progression": "Campaign Core",
            "persistence": "CampaignSave.dat",
            "remote_pre_request": "retired",
            "remote_post_request": "retired before serializer/network",
            "CampaignObjectives.dat": "not required by v3",
        },
        "verified_post_layout": {
            "+0x68": "star1",
            "+0x69": "star2",
            "+0x6A": "star3",
            "+0x78": "position_in_race",
            "+0x7C": "race_time",
        },
        "sha256_before": before,
        "sha256_after": sha(ams),
        "core_sha256": sha(target_core),
        "backup": str(backup),
        "changes": changes,
    }
    report.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[OK] Campaign Career Adapter v3 applied.")
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
