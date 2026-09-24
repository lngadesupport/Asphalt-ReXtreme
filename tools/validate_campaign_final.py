#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pe_info(path: Path):
    d = path.read_bytes()
    if d[:2] != b"MZ":
        return {"valid": False, "reason": "not MZ"}
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    if d[pe:pe+4] != b"PE\0\0":
        return {"valid": False, "reason": "bad PE"}
    machine = struct.unpack_from("<H", d, pe + 4)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", d, opt)[0]
    entry = struct.unpack_from("<I", d, opt + 16)[0]
    return {
        "valid": True,
        "machine": machine,
        "optional_magic": magic,
        "entry_rva": entry,
        "x86_pe32": machine == 0x14C and magic == 0x10B,
        "no_entry": entry == 0,
    }


def load_module(path: Path, name: str):
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def bytes_at(data: bytes, off: int, size: int) -> bytes:
    return data[off:off+size]


def patch_status(root: Path, ams_data: bytes):
    tools = root / "tools"
    result = {}

    g = load_module(tools / "campaign_garage_v2.py", "cg")
    if g:
        gateway, owned_va = g.build_gateway()
        build_patch = b"\xE9" + g.rel32(g.BUILD_VA, 5, g.CAVE_VA)
        owned_patch = b"\xE9" + g.rel32(g.OWN_VA, 5, owned_va)
        result["garage"] = {
            "ready": (
                bytes_at(ams_data, g.BUILD_OFF, 5) == build_patch
                and bytes_at(ams_data, g.OWN_OFF, 5) == owned_patch
                and bytes_at(ams_data, g.CAVE_OFF, g.CAVE_LEN) == gateway
            )
        }

    c = load_module(tools / "campaign_career_adapter_v2.py", "cc")
    if c:
        result["career"] = {
            "ready": (
                bytes_at(ams_data, c.PRE_SITE_OFF, 5) == c.PRE_SITE_PATCH
                and bytes_at(ams_data, c.PRE_STUB_OFF, len(c.PRE_STUB)) == c.PRE_STUB
                and bytes_at(ams_data, c.POST_FACTORY_OFF, len(c.POST_FACTORY_STUB)) == c.POST_FACTORY_STUB
                and bytes_at(ams_data, c.POST_NOTIFY_OFF, len(c.POST_NOTIFY_STUB)) == c.POST_NOTIFY_STUB
            )
        }

    u = load_module(tools / "campaign_upgrade_adapter_v1.py", "cu")
    if u:
        result["upgrade"] = {
            "ready": bytes_at(ams_data, u.SITE_OFF, len(u.PATCHED)) == u.PATCHED
        }

    s = load_module(tools / "campaign_store_adapter_v1.py", "cs")
    if s:
        result["store"] = {
            "ready": (
                bytes_at(ams_data, s.CONTROLLER_OFF, 5) == s.CONTROLLER_PATCH
                and bytes_at(ams_data, s.STUB_OFF, len(s.STUB_PATCH)) == s.STUB_PATCH
            )
        }

    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    ns = ap.parse_args()

    root = ns.project_root.resolve()
    pkg = root / "_PACKAGE_PHASE5"
    output = ns.output or (root / "_TRACE_MONTAR" / "CAMPAIGN-FINAL-STATUS.json")
    output.parent.mkdir(parents=True, exist_ok=True)

    ams = pkg / "AMS.exe"
    core = pkg / "IGPLib_x86.dll"

    report = {
        "edition": "Asphalt ReXtreme Campaign Edition",
        "root": str(root),
        "core": {},
        "data": {},
        "patches": {},
        "runtime_hygiene": {},
        "playable_ready": False,
        "complete_rebuild": False,
        "blocking": [],
    }

    if not ams.is_file():
        report["blocking"].append("AMS.exe missing")
    if not core.is_file():
        report["blocking"].append("IGPLib_x86.dll missing")

    if core.is_file():
        info = pe_info(core)
        raw = core.read_bytes()
        report["core"] = {
            **info,
            "size": core.stat().st_size,
            "sha256": sha(core),
            "crt_strings_present": any(x in raw for x in (b"VCRUNTIME", b"MSVCP", b"ucrtbase")),
        }
        if not info.get("x86_pe32") or not info.get("no_entry"):
            report["blocking"].append("Campaign Core is not x86 PE32 /NOENTRY")
        if report["core"]["crt_strings_present"]:
            report["blocking"].append("Campaign Core appears to reference CRT")

    required = [
        "CampaignCatalog.dat",
        "CampaignEvents.dat",
        "CampaignObjectives.dat",
        "CampaignUpgrades.dat",
        "CampaignUpgradeUiMap.dat",
        "CampaignStore.dat",
    ]
    for name in required:
        p = pkg / name
        count = None
        if p.is_file() and p.stat().st_size >= 12:
            try:
                count = struct.unpack_from("<I", p.read_bytes(), 8)[0]
            except Exception:
                count = None
        report["data"][name] = {
            "exists": p.is_file(),
            "size": p.stat().st_size if p.is_file() else 0,
            "sha256": sha(p) if p.is_file() else None,
            "entry_count": count,
        }

    for name in ("CampaignCatalog.dat", "CampaignEvents.dat", "CampaignObjectives.dat", "CampaignUpgrades.dat"):
        if not report["data"][name]["exists"]:
            report["blocking"].append(f"{name} missing")

    if ams.is_file():
        ams_data = ams.read_bytes()
        report["patches"] = patch_status(root, ams_data)
        offline_off = 0x00BACDD0
        offline_expected = bytes.fromhex("31 C0 C3 90 90 90 90")
        report["service_retirement"] = {
            "global_is_online_false": bytes_at(
                ams_data, offline_off, len(offline_expected)
            ) == offline_expected,
            "global_is_online_file_offset": f"0x{offline_off:08X}",
        }
        if not report["service_retirement"]["global_is_online_false"]:
            report["blocking"].append("Global IsOnline FALSE patch missing")

    runtime_dll = pkg / "ReXtremeLocalRuntime.dll"
    report["runtime_hygiene"] = {
        "legacy_runtime_dll_present": runtime_dll.exists(),
        "legacy_runtime_dll": str(runtime_dll),
    }
    if runtime_dll.exists():
        report["blocking"].append("legacy ReXtremeLocalRuntime.dll still present")

    for subsystem in ("garage", "career"):
        if subsystem in report["patches"] and not report["patches"][subsystem]["ready"]:
            report["blocking"].append(f"{subsystem} adapter not applied")

    # Upgrade/store can be intentionally offline-disabled if their strict data
    # mapping was not reconstructed; report separately rather than claiming ready.
    report["subsystems"] = {
        "garage": "READY" if report["patches"].get("garage", {}).get("ready") else "NOT_APPLIED",
        "career": "READY" if report["patches"].get("career", {}).get("ready") else "NOT_APPLIED",
        "upgrade": (
            "READY"
            if report["patches"].get("upgrade", {}).get("ready")
               and (report["data"]["CampaignUpgradeUiMap.dat"]["entry_count"] or 0) > 0
            else "BLOCKED_DATA"
            if not report["data"]["CampaignUpgradeUiMap.dat"]["exists"]
               or (report["data"]["CampaignUpgradeUiMap.dat"]["entry_count"] or 0) == 0
            else "NOT_APPLIED"
        ),
        "store": (
            "READY"
            if report["patches"].get("store", {}).get("ready")
               and (report["data"]["CampaignStore.dat"]["entry_count"] or 0) > 0
            else "MONETIZATION_RETIRED"
            if report["patches"].get("store", {}).get("ready")
               and (report["data"]["CampaignStore.dat"]["entry_count"] or 0) == 0
            else "BLOCKED_DATA"
            if not report["data"]["CampaignStore.dat"]["exists"]
            else "NOT_APPLIED"
        ),
    }

    report["playable_ready"] = len(report["blocking"]) == 0

    complete_states = report.get("subsystems", {})
    report["complete_rebuild"] = (
        report["playable_ready"]
        and complete_states.get("garage") == "READY"
        and complete_states.get("career") == "READY"
        and complete_states.get("upgrade") == "READY"
        and complete_states.get("store") == "READY"
    )

    if not report["complete_rebuild"]:
        report["completion_gaps"] = [
            name for name, state in complete_states.items()
            if state != "READY"
        ]
    else:
        report["completion_gaps"] = []

    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Return success for a stable playable Campaign build. The JSON separately
    # states whether the literal full rebuild is complete.
    return 0 if report["playable_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
