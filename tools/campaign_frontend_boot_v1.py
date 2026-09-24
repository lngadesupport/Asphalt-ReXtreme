#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, struct
from pathlib import Path

IMAGE_BASE = 0x00400000
IGP_HTTPPOST_IAT_RVA = 0x0112A034
IGP_HTTPPOST_PREF_VA = IMAGE_BASE + IGP_HTTPPOST_IAT_RVA

ONLINE_OFF = 0x00BACDD0
ONLINE_FALSE = bytes.fromhex("31 C0 C3 90 90 90 90")

PROFILE1_OFF = 0x0069B8C6
PROFILE1_ORIG = bytes.fromhex("74 24")
PROFILE1_LOCAL = bytes.fromhex("74 22")

PROFILE2_OFF = 0x0069B8E6
PROFILE2_ORIG = bytes.fromhex("32 C0")
PROFILE2_LOCAL = bytes.fromhex("B0 01")

AGE1_OFF = 0x006A1CE1
AGE1_ORIG = bytes.fromhex("0F 85 FE 00 00 00")
AGE1_LOCAL = bytes.fromhex("E9 FF 00 00 00 90")

AGE2_OFF = 0x006A1E03
AGE2_ORIG = bytes.fromhex("0F 85 D8 00 00 00")
AGE2_LOCAL = bytes.fromhex("E9 D9 00 00 00 90")

BOOT_SITE_OFF = 0x0092B82A
BOOT_SITE_VA = BOOT_SITE_OFF + 0x00400C00
BOOT_SITE_ORIG = bytes.fromhex("0F 84 8D 01 00 00")
BOOT_RESUME_VA = 0x00D2C5BD

LOBBY_SITE_OFF = 0x009171DC
LOBBY_SITE_VA = LOBBY_SITE_OFF + 0x00400C00
LOBBY_SITE_ORIG = bytes.fromhex("51 8B CC C6 45")
LOBBY_RESUME_VA = 0x00D18009

POPUP_OFF = 0x009168B0
POPUP_ORIG = bytes.fromhex("55 8B EC 6A FF")
POPUP_RETIRED = bytes.fromhex("31 C0 C2 18 00")

CAVE_OFF = 0x004693C1
CAVE_VA = 0x00869FC1
CAVE_LEN = 47
CAVE_FREE = b"\xCC" * CAVE_LEN

FRONTEND_BOOT_MAGIC = 0xC0DE7710
FRONTEND_LOBBY_MAGIC = 0xC0DE7711

def fmt(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)

def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def rel32(src_va: int, insn_len: int, dst_va: int) -> bytes:
    d = dst_va - (src_va + insn_len)
    if not (-0x80000000 <= d <= 0x7fffffff):
        raise RuntimeError("rel32 out of range")
    return struct.pack("<i", d)

def build_stub(stub_va: int, selector: int, resume_va: int) -> bytes:
    code = bytearray()
    code += b"\x68" + struct.pack("<I", selector)
    call_va = stub_va + len(code)
    code += b"\xE8\x00\x00\x00\x00"
    return_va = call_va + 5
    code += b"\x58"
    code += b"\x05" + struct.pack("<I", (IGP_HTTPPOST_PREF_VA - return_va) & 0xffffffff)
    code += b"\xFF\x10"
    jmp_va = stub_va + len(code)
    code += b"\xE9" + rel32(jmp_va, 5, resume_va)
    return bytes(code)

BOOT_STUB = build_stub(CAVE_VA, FRONTEND_BOOT_MAGIC, BOOT_RESUME_VA)
LOBBY_STUB_VA = CAVE_VA + len(BOOT_STUB)
LOBBY_STUB = build_stub(LOBBY_STUB_VA, FRONTEND_LOBBY_MAGIC, LOBBY_RESUME_VA)
CAVE_PATCH = BOOT_STUB + LOBBY_STUB
if len(CAVE_PATCH) > CAVE_LEN:
    raise RuntimeError(f"frontend boot/lobby stubs exceed cave: {len(CAVE_PATCH)} > {CAVE_LEN}")
CAVE_PATCH += b"\xCC" * (CAVE_LEN - len(CAVE_PATCH))

BOOT_SITE_PATCH = b"\xE9" + rel32(BOOT_SITE_VA, 5, CAVE_VA) + b"\x90"
LOBBY_SITE_PATCH = b"\xE9" + rel32(LOBBY_SITE_VA, 5, LOBBY_STUB_VA)

def patch(d: bytearray, off: int, before: bytes, after: bytes, label: str, changes: list[dict]):
    cur = bytes(d[off:off+len(before)])
    if cur == after:
        changes.append({"label": label, "offset": f"0x{off:08X}", "status": "already-patched"})
        return
    if cur != before:
        raise RuntimeError(f"{label}: unexpected bytes at 0x{off:08X}: {fmt(cur)}")
    d[off:off+len(before)] = after
    changes.append({
        "label": label, "offset": f"0x{off:08X}", "status": "patched",
        "before": fmt(before), "after": fmt(after)
    })

def apply(root: Path) -> int:
    ams = root / "_PACKAGE_PHASE5" / "AMS.exe"
    if not ams.is_file():
        raise FileNotFoundError(ams)

    raw = ams.read_bytes()
    if raw[ONLINE_OFF:ONLINE_OFF+len(ONLINE_FALSE)] != ONLINE_FALSE:
        raise RuntimeError("Global IsOnline is not FALSE")

    d = bytearray(raw)
    changes: list[dict] = []

    patch(d, PROFILE1_OFF, PROFILE1_ORIG, PROFILE1_LOCAL,
          "frontend profile presentation validation 1", changes)
    patch(d, PROFILE2_OFF, PROFILE2_ORIG, PROFILE2_LOCAL,
          "frontend profile presentation validation 2", changes)
    patch(d, AGE1_OFF, AGE1_ORIG, AGE1_LOCAL,
          "frontend age UI -> local continuation 1", changes)
    patch(d, AGE2_OFF, AGE2_ORIG, AGE2_LOCAL,
          "frontend age UI -> local continuation 2", changes)

    cave_cur = bytes(d[CAVE_OFF:CAVE_OFF+CAVE_LEN])
    if cave_cur not in (CAVE_FREE, CAVE_PATCH):
        raise RuntimeError("frontend bridge cave is not free: " + fmt(cave_cur))
    if cave_cur == CAVE_FREE:
        d[CAVE_OFF:CAVE_OFF+CAVE_LEN] = CAVE_PATCH
        changes.append({
            "label": "install frontend-only BOOT + LOBBY bridge stubs",
            "offset": f"0x{CAVE_OFF:08X}",
            "status": "patched",
            "boot_magic": f"0x{FRONTEND_BOOT_MAGIC:08X}",
            "lobby_magic": f"0x{FRONTEND_LOBBY_MAGIC:08X}"
        })

    patch(d, BOOT_SITE_OFF, BOOT_SITE_ORIG, BOOT_SITE_PATCH,
          "remote profile startup -> CampaignFrontendBoot", changes)
    patch(d, LOBBY_SITE_OFF, LOBBY_SITE_ORIG, LOBBY_SITE_PATCH,
          "legacy lobby no-internet block -> CampaignFrontendLobbyReady", changes)
    patch(d, POPUP_OFF, POPUP_ORIG, POPUP_RETIRED,
          "retire legacy GS_MessagePopup service UI", changes)

    before = sha(raw)
    bdir = root / "_BACKUPS" / "FRONTEND-ONLY-BOOT-V1"
    bdir.mkdir(parents=True, exist_ok=True)
    bak = bdir / f"AMS.exe.{before}.bak"
    if not bak.exists():
        shutil.copy2(ams, bak)

    tmp = ams.with_suffix(".frontend-boot-v1.tmp")
    tmp.write_bytes(d)
    verify = tmp.read_bytes()

    checks = (
        (CAVE_OFF, CAVE_PATCH, "bridge cave"),
        (BOOT_SITE_OFF, BOOT_SITE_PATCH, "boot site"),
        (LOBBY_SITE_OFF, LOBBY_SITE_PATCH, "lobby site"),
        (POPUP_OFF, POPUP_RETIRED, "legacy popup retirement"),
    )
    for off, expected, label in checks:
        if verify[off:off+len(expected)] != expected:
            raise RuntimeError(f"verification failed: {label}")

    tmp.replace(ams)

    out = root / "_TRACE_MONTAR"
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "phase": "Frontend-Only Boot/Profile/Lobby v1",
        "authority": "CampaignFrontendBridge / CampaignServices",
        "legacy_network_authority": False,
        "global_is_online": False,
        "legacy_service_popup": "retired via ABI-safe ret 0x18",
        "boot": {
            "source": "legacy remote-profile startup boundary",
            "replacement": "CampaignFrontendBoot",
            "selector": f"0x{FRONTEND_BOOT_MAGIC:08X}"
        },
        "lobby": {
            "source": "legacy NO_INTERNET lobby boundary",
            "replacement": "CampaignFrontendLobbyReady",
            "selector": f"0x{FRONTEND_LOBBY_MAGIC:08X}"
        },
        "frontend_profile_object": "presentation glue only; not campaign authority",
        "garage_career_upgrade_store": "not applied in this test",
        "sha256_before": before,
        "sha256_after": sha(ams.read_bytes()),
        "backup": str(bak),
        "changes": changes
    }
    rp = out / "FRONTEND-ONLY-BOOT-V1.json"
    rp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[OK] Frontend-Only Boot/Profile/Lobby v1 applied.")
    print("[BOOT] remote profile boundary -> CampaignFrontendBoot")
    print("[LOBBY] legacy no-internet boundary -> CampaignFrontendLobbyReady")
    print("[UI] legacy service popup wrapper -> RETIRED (ABI-safe)")
    print("[NETWORK] Global IsOnline -> FALSE")
    print(f"[AMS] {report['sha256_after']}")
    print(f"[REPORT] {rp}")
    return 0

def main() -> int:
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
