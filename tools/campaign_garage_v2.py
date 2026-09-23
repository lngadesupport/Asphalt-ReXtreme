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

BUILD_OFF = 0x00686D60
BUILD_VA = 0x00A87960
BUILD_ORIG = bytes.fromhex("55 8B EC 6A FF")
BUILD_R18 = bytes.fromhex("C3 90 90 90 90")

OWN_OFF = 0x00A524E0
OWN_VA = 0x00E530E0
OWN_ORIG = bytes.fromhex("55 8B EC 8B 51")

R15_OFF = 0x00686DA4
R15_ORIG = bytes.fromhex("0F 85 DE 01 00 00")
R15_PATCH = bytes.fromhex("E9 DF 01 00 00 90")

P39_START_OFF = 0x005A3FA0
P39_START_ORIG = bytes.fromhex("FF 71 68 E8 08 00 00 00 C3 CC")
P39_START_PATCH = bytes.fromhex("6A 00 6A 00 E8 F7 FC FF FF C3")

P39_HANDLER_OFF = 0x005A3CB6
P39_HANDLER_ORIG = bytes.fromhex("56 FF 75 08 8B F9 E8 2F FF 3F 00")
P39_HANDLER_PATCH = bytes.fromhex("8B F9 31 C0 E9 89 01 00 00 90 90")

P48_SITE_OFF = 0x00687110
P48_SITE_ORIG = bytes.fromhex("8B 55 EC 8B CE")
P48_SITE_PATCH = bytes.fromhex("E9 AC 22 DE FF")

P48_CAVE_OFF = 0x004693C1
P48_CAVE_LEN = 47
P48_CAVE_ORIG = b"\xCC" * P48_CAVE_LEN
P48_STUB = bytes([
    0x8B,0x4D,0xEC,
    0x6A,0x00,
    0x6A,0x00,
    0x6A,0x00,
    0xE8,0x31,0xAD,0x23,0x00,
    0xE9,0x68,0xDD,0x21,0x00,
]) + b"\xCC" * (P48_CAVE_LEN - 19)

POPUP_OFF = 0x009168B0
POPUP_EXPECTED_STATES = (
    bytes.fromhex("55 8B EC 6A FF"),
    bytes.fromhex("31 C0 C2 18 00"),
)
POPUP_PATCH = bytes.fromhex("31 C0 C2 18 00")

ONLINE_OFF = 0x00BACDD0
ONLINE_FALSE = bytes.fromhex("31 C0 C3 90 90 90 90")

CAVE_OFF = 0x004693C1
CAVE_VA = 0x00869FC1
CAVE_LEN = 47

CRAFT_MAGIC = 0xC0DEC0DE
OWNED_MAGIC = 0xC0DE0A11


def fmt(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel32(src_va: int, insn_len: int, dst_va: int) -> bytes:
    delta = dst_va - (src_va + insn_len)
    if not (-0x80000000 <= delta <= 0x7FFFFFFF):
        raise RuntimeError("rel32 out of range")
    return struct.pack("<i", delta)


def u16(d: bytes, o: int) -> int:
    return struct.unpack_from("<H", d, o)[0]


def u32(d: bytes, o: int) -> int:
    return struct.unpack_from("<I", d, o)[0]


def validate_pe(d: bytes) -> None:
    if d[:2] != b"MZ":
        raise RuntimeError("AMS.exe is not MZ")
    pe = u32(d, 0x3C)
    if d[pe:pe+4] != b"PE\0\0":
        raise RuntimeError("invalid PE signature")
    if u16(d, pe + 4) != 0x014C:
        raise RuntimeError("expected x86 PE")
    opt = pe + 24
    if u16(d, opt) != 0x010B:
        raise RuntimeError("expected PE32")
    if u32(d, opt + 28) != IMAGE_BASE:
        raise RuntimeError("unexpected preferred image base")


def build_gateway() -> tuple[bytes, int]:
    craft = bytearray()
    craft += b"\x68" + struct.pack("<I", CRAFT_MAGIC)
    craft += b"\xE8\x00\x00\x00\x00"
    craft += b"\x58"
    craft_pop_next = CAVE_VA + len(craft)
    craft += b"\x05" + struct.pack("<I", IGP_HTTPPOST_PREF_VA - craft_pop_next)
    craft += b"\xFF\x10"
    craft += b"\xC3"

    owned_va = CAVE_VA + len(craft)
    owned = bytearray()
    owned += bytes.fromhex("8B 44 24 04")      # eax = pointer argument
    owned += bytes.fromhex("8B 08")            # ecx = car_id
    owned += b"\x68" + struct.pack("<I", OWNED_MAGIC)
    owned += b"\xE8\x00\x00\x00\x00"
    owned += b"\x58"
    owned_pop_next = owned_va + len(owned)
    owned += b"\x05" + struct.pack("<I", IGP_HTTPPOST_PREF_VA - owned_pop_next)
    owned += b"\xFF\x10"
    owned += bytes.fromhex("C2 04 00")

    result = bytes(craft + owned)
    if len(result) > CAVE_LEN:
        raise RuntimeError("Campaign gateway exceeds reserved cave")
    result += b"\xCC" * (CAVE_LEN - len(result))
    return result, owned_va


def normalize_known_old_experiments(data: bytearray, changes: list[dict]) -> None:
    # R15 is obsolete once BuildCar itself becomes the Campaign entry.
    cur = bytes(data[R15_OFF:R15_OFF+len(R15_ORIG)])
    if cur == R15_PATCH:
        data[R15_OFF:R15_OFF+len(R15_ORIG)] = R15_ORIG
        changes.append({"label": "retire R15 routing", "offset": f"0x{R15_OFF:08X}",
                        "before": fmt(R15_PATCH), "after": fmt(R15_ORIG)})
    elif cur != R15_ORIG:
        raise RuntimeError(f"unknown R15 site: {fmt(cur)}")

    # Phase39 is no longer reachable/needed; restore its original code.
    for label, off, orig, oldpatch in (
        ("retire Phase39 CraftCar start", P39_START_OFF, P39_START_ORIG, P39_START_PATCH),
        ("retire Phase39 result handler", P39_HANDLER_OFF, P39_HANDLER_ORIG, P39_HANDLER_PATCH),
    ):
        cur = bytes(data[off:off+len(orig)])
        if cur == oldpatch:
            data[off:off+len(orig)] = orig
            changes.append({"label": label, "offset": f"0x{off:08X}",
                            "before": fmt(oldpatch), "after": fmt(orig)})
        elif cur != orig:
            raise RuntimeError(f"{label}: unknown bytes {fmt(cur)}")

    # Phase48 used the same cave. Remove it only if its exact known bytes exist.
    site = bytes(data[P48_SITE_OFF:P48_SITE_OFF+5])
    cave = bytes(data[P48_CAVE_OFF:P48_CAVE_OFF+P48_CAVE_LEN])
    if site == P48_SITE_PATCH:
        if cave != P48_STUB:
            raise RuntimeError("Phase48 site is active but its cave does not match")
        data[P48_SITE_OFF:P48_SITE_OFF+5] = P48_SITE_ORIG
        data[P48_CAVE_OFF:P48_CAVE_OFF+P48_CAVE_LEN] = P48_CAVE_ORIG
        changes.append({"label": "retire Phase48 completion hook",
                        "offset": f"0x{P48_SITE_OFF:08X}",
                        "before": fmt(P48_SITE_PATCH), "after": fmt(P48_SITE_ORIG)})
    elif site != P48_SITE_ORIG:
        raise RuntimeError(f"unknown Phase48 hook site: {fmt(site)}")


def apply(root: Path) -> int:
    ams = root / "_PACKAGE_PHASE5" / "AMS.exe"
    core = root / "prebuilt" / "campaign-core" / "IGPLib_x86.dll"
    target_core = root / "_PACKAGE_PHASE5" / "IGPLib_x86.dll"

    if not ams.is_file():
        raise FileNotFoundError(f"AMS.exe not found: {ams}")
    if not core.is_file():
        raise FileNotFoundError(f"Campaign Core v2 DLL not found: {core}")

    data = bytearray(ams.read_bytes())
    validate_pe(data)
    before = sha(data)
    changes: list[dict] = []

    gateway, owned_stub_va = build_gateway()
    expected_build_patch = b"\xE9" + rel32(BUILD_VA, 5, CAVE_VA)
    expected_owned_patch = b"\xE9" + rel32(OWN_VA, 5, owned_stub_va)

    # Already applied is allowed if all routing bytes match.
    build_cur = bytes(data[BUILD_OFF:BUILD_OFF+5])
    own_cur = bytes(data[OWN_OFF:OWN_OFF+5])
    cave_cur = bytes(data[CAVE_OFF:CAVE_OFF+CAVE_LEN])

    if build_cur == expected_build_patch and own_cur == expected_owned_patch and cave_cur == gateway:
        shutil.copy2(core, target_core)
        print("[OK] CampaignGarage v2 already applied; Campaign Core v2 refreshed.")
        return 0

    # R18 RET can be normalized to the original entry guard because only the
    # first 5 bytes matter before we install the new JMP.
    if build_cur == BUILD_R18:
        data[BUILD_OFF:BUILD_OFF+5] = BUILD_ORIG
        changes.append({"label": "retire R18 BuildCar RET", "offset": f"0x{BUILD_OFF:08X}",
                        "before": fmt(BUILD_R18), "after": fmt(BUILD_ORIG)})
        build_cur = BUILD_ORIG

    if build_cur != BUILD_ORIG:
        raise RuntimeError(f"BuildCar entry unknown: {fmt(build_cur)}")
    if own_cur != OWN_ORIG:
        raise RuntimeError(f"ownership query entry unknown: {fmt(own_cur)}")

    normalize_known_old_experiments(data, changes)

    popup_cur = bytes(data[POPUP_OFF:POPUP_OFF+5])
    if popup_cur not in POPUP_EXPECTED_STATES:
        raise RuntimeError(f"sync popup site unknown: {fmt(popup_cur)}")
    if popup_cur != POPUP_PATCH:
        data[POPUP_OFF:POPUP_OFF+5] = POPUP_PATCH
        changes.append({"label": "retire obsolete sync-error popup",
                        "offset": f"0x{POPUP_OFF:08X}",
                        "before": fmt(popup_cur), "after": fmt(POPUP_PATCH)})

    online_cur = bytes(data[ONLINE_OFF:ONLINE_OFF+len(ONLINE_FALSE)])
    if online_cur != ONLINE_FALSE:
        raise RuntimeError(
            "Global IsOnline is not in the expected Campaign offline state: "
            + fmt(online_cur)
        )

    if bytes(data[CAVE_OFF:CAVE_OFF+CAVE_LEN]) != P48_CAVE_ORIG:
        raise RuntimeError("reserved Campaign gateway cave is not free")

    data[CAVE_OFF:CAVE_OFF+CAVE_LEN] = gateway
    data[BUILD_OFF:BUILD_OFF+5] = expected_build_patch
    data[OWN_OFF:OWN_OFF+5] = expected_owned_patch

    changes += [
        {"label": "install Campaign Core position-independent gateway",
         "offset": f"0x{CAVE_OFF:08X}", "before": fmt(P48_CAVE_ORIG), "after": fmt(gateway)},
        {"label": "MONTAR -> CampaignCraftInvoke",
         "offset": f"0x{BUILD_OFF:08X}", "before": fmt(BUILD_ORIG), "after": fmt(expected_build_patch)},
        {"label": "ownership membership -> CampaignIsOwned",
         "offset": f"0x{OWN_OFF:08X}", "before": fmt(OWN_ORIG), "after": fmt(expected_owned_patch)},
    ]

    backup_dir = root / "_BACKUPS" / "CAMPAIGN-GARAGE-V2"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"AMS.exe.{before}.bak"
    if not backup.exists():
        shutil.copy2(ams, backup)

    tmp = ams.with_suffix(".campaign-v2.tmp")
    tmp.write_bytes(data)

    verify = tmp.read_bytes()
    if (verify[BUILD_OFF:BUILD_OFF+5] != expected_build_patch or
        verify[OWN_OFF:OWN_OFF+5] != expected_owned_patch or
        verify[CAVE_OFF:CAVE_OFF+CAVE_LEN] != gateway):
        tmp.unlink(missing_ok=True)
        raise RuntimeError("verification failed before replace")

    tmp.replace(ams)
    shutil.copy2(core, target_core)

    report = {
        "phase": "CampaignGarage v2",
        "architecture": "x86",
        "old_craftcar_reachable_from_MONTAR": False,
        "buildcar": {"va": f"0x{BUILD_VA:08X}", "file_offset": f"0x{BUILD_OFF:08X}"},
        "ownership_query": {"va": f"0x{OWN_VA:08X}", "file_offset": f"0x{OWN_OFF:08X}"},
        "gateway": {"va": f"0x{CAVE_VA:08X}", "file_offset": f"0x{CAVE_OFF:08X}",
                    "iat_rva": f"0x{IGP_HTTPPOST_IAT_RVA:08X}", "aslr_safe": True},
        "campaign_core": str(core),
        "backup": str(backup),
        "sha256_before": before,
        "sha256_after": sha(ams.read_bytes()),
        "changes": changes,
        "stage1_semantics": "MONTAR performs local selected-car acquisition in Campaign Core v2; recipe catalog binding follows in CampaignGarage v3.",
    }

    out = root / "_TRACE_MONTAR"
    out.mkdir(parents=True, exist_ok=True)
    rp = out / "CAMPAIGN-GARAGE-V2.json"
    rp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[OK] CampaignGarage v2 applied.")
    print(f"[AMS] {report['sha256_after']}")
    print(f"[CORE] {target_core}")
    print(f"[BACKUP] {backup}")
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
