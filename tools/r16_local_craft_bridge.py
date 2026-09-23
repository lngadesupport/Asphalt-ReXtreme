#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from datetime import datetime
from pathlib import Path

# R16 LocalCraft runtime bridge.
#
# Stage 1: preserve CraftCar_Caller's already-created operation but skip the
#          dead backend request call.
# Stage 2: at the end of GS_Garage::BuildCar, after the listener is registered
#          and GS virtual +0x54 has run, dispatch the original garage listener
#          with status=0 and a null shared context.
#
# All injected control flow is rel32 and therefore ASLR-safe.

IMAGE_BASE_EXPECTED = 0x00400000

# R15 prerequisite.
R15_OFF = 0x00686DA4
R15_BYTES = bytes.fromhex("E9 DF 01 00 00 90")

# CraftCar_Caller: call 0x009A4BA0 at VA 0x009A00ED.
NET_CALL_OFF = 0x0059F4ED
NET_CALL_VA = 0x009A00ED
NET_CALL_ORIG = bytes.fromhex("E8 AE 4A 00 00")
NET_CALL_PATCH = bytes.fromhex("90 90 90 90 90")

# GS_Garage::BuildCar near the end:
#   8B 03       mov eax,[ebx]
#   8B CB       mov ecx,ebx
#   FF 50 54    call dword ptr [eax+54h]
# Hook replaces all 7 bytes and the cave replays them before local success.
HOOK_OFF = 0x00687168
HOOK_VA = 0x00A87D68
HOOK_ORIG = bytes.fromhex("8B 03 8B CB FF 50 54")
HOOK_LEN = len(HOOK_ORIG)
HOOK_RETURN_VA = HOOK_VA + HOOK_LEN

GARAGE_LISTENER_CALLBACK_VA = 0x00AA4D00
GARAGE_LISTENER_SUBOBJECT_OFF = 0x298

CAVE_MIN = 48
STATE_REL = Path("_BACKUPS") / "R16" / "state.json"
REPORT_REL = Path("_TRACE_MONTAR") / "R16-LOCAL-CRAFT-BRIDGE.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fmt(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def s32(n: int) -> bytes:
    if not (-0x80000000 <= n <= 0x7FFFFFFF):
        raise ValueError(f"rel32 out of range: {n}")
    return struct.pack("<i", n)


def rel32(src_va: int, insn_len: int, dst_va: int) -> bytes:
    return s32(dst_va - (src_va + insn_len))


def pe_sections(data: bytes):
    if data[:2] != b"MZ":
        raise ValueError("not an MZ/PE image")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe+4] != b"PE\0\0":
        raise ValueError("invalid PE signature")

    machine, count = struct.unpack_from("<HH", data, pe + 4)
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    if magic != 0x10B:
        raise ValueError(f"expected PE32/x86, optional magic=0x{magic:04X}")

    image_base = struct.unpack_from("<I", data, opt + 28)[0]
    sec_table = opt + opt_size
    out = []
    for i in range(count):
        o = sec_table + i * 40
        name = data[o:o+8].split(b"\0",1)[0].decode("ascii","replace")
        virtual_size, virtual_address, raw_size, raw_ptr = struct.unpack_from("<IIII", data, o + 8)
        characteristics = struct.unpack_from("<I", data, o + 36)[0]
        out.append({
            "name": name,
            "virtual_size": virtual_size,
            "virtual_address": virtual_address,
            "raw_size": raw_size,
            "raw_ptr": raw_ptr,
            "characteristics": characteristics,
        })
    return image_base, out


def off_to_va(image_base: int, sections, off: int) -> int:
    for s in sections:
        lo, hi = s["raw_ptr"], s["raw_ptr"] + s["raw_size"]
        if lo <= off < hi:
            return image_base + s["virtual_address"] + (off - lo)
    raise ValueError(f"file offset 0x{off:X} is not in a PE section")


def find_exec_cc_cave(data: bytes, image_base: int, sections, min_len=CAVE_MIN):
    # Search backwards so we prefer late padding and avoid early function
    # alignment areas. Only executable sections are considered.
    reserved = [
        (NET_CALL_OFF - 0x100, NET_CALL_OFF + 0x100),
        (HOOK_OFF - 0x100, HOOK_OFF + 0x100),
        (R15_OFF - 0x100, R15_OFF + 0x100),
    ]
    for s in reversed(sections):
        if not (s["characteristics"] & 0x20000000):  # IMAGE_SCN_MEM_EXECUTE
            continue
        lo = s["raw_ptr"]
        hi = min(len(data), lo + s["raw_size"])
        i = hi - min_len
        while i >= lo:
            if data[i:i+min_len] == b"\xCC" * min_len:
                if not any(a <= i < b or a < i + min_len <= b for a,b in reserved):
                    return i, off_to_va(image_base, sections, i)
            i -= 1
    raise RuntimeError(f"no executable 0xCC cave of {min_len} bytes found")


def build_stub(cave_va: int) -> bytes:
    b = bytearray()

    # Replay overwritten BuildCar instructions:
    #   mov eax,[ebx]
    #   mov ecx,ebx
    #   call dword ptr [eax+54h]
    b += bytes.fromhex("8B 03 8B CB FF 50 54")

    # Original result callback ABI:
    # stack after CALL: [ret][status][ctx.object][ctx.control]
    # push control=0, object=0, status=0
    b += bytes.fromhex("6A 00 6A 00 6A 00")

    # ecx = &GS_Garage::listener_subobject (GS + 0x298)
    b += bytes.fromhex("8D 8B 98 02 00 00")

    # call GS_Garage listener slot4 implementation 0x00AA4D00
    call_va = cave_va + len(b)
    b += b"\xE8" + rel32(call_va, 5, GARAGE_LISTENER_CALLBACK_VA)

    # Continue BuildCar immediately after the overwritten 7 bytes.
    jmp_va = cave_va + len(b)
    b += b"\xE9" + rel32(jmp_va, 5, HOOK_RETURN_VA)
    return bytes(b)


def hook_bytes(cave_va: int) -> bytes:
    return b"\xE9" + rel32(HOOK_VA, 5, cave_va) + b"\x90\x90"


def load(root: Path):
    exe = root / "_PACKAGE_PHASE5" / "AMS.exe"
    if not exe.is_file():
        raise FileNotFoundError(f"AMS.exe nao encontrado: {exe}")
    return exe, bytearray(exe.read_bytes())


def write_json(root: Path, rel: Path, obj):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def plan(root: Path):
    exe, data = load(root)
    image_base, sections = pe_sections(data)
    cave_off, cave_va = find_exec_cc_cave(data, image_base, sections)
    stub = build_stub(cave_va)
    hpatch = hook_bytes(cave_va)

    cur_r15 = bytes(data[R15_OFF:R15_OFF+len(R15_BYTES)])
    cur_net = bytes(data[NET_CALL_OFF:NET_CALL_OFF+len(NET_CALL_ORIG)])
    cur_hook = bytes(data[HOOK_OFF:HOOK_OFF+HOOK_LEN])

    can = (
        cur_r15 == R15_BYTES
        and cur_net in (NET_CALL_ORIG, NET_CALL_PATCH)
        and cur_hook in (HOOK_ORIG, hpatch)
        and data[cave_off:cave_off+len(stub)] in (b"\xCC"*len(stub), stub)
    )

    report = {
        "name": "R16 LocalCraft Runtime Bridge",
        "action": "plan",
        "created_at": datetime.now().isoformat(),
        "exe": str(exe),
        "sha256": sha256(data),
        "image_base": f"0x{image_base:08X}",
        "r15_present": cur_r15 == R15_BYTES,
        "network_call": {
            "va": f"0x{NET_CALL_VA:08X}",
            "file_offset": f"0x{NET_CALL_OFF:08X}",
            "original": fmt(NET_CALL_ORIG),
            "patched": fmt(NET_CALL_PATCH),
            "current": fmt(cur_net),
        },
        "completion_hook": {
            "va": f"0x{HOOK_VA:08X}",
            "return_va": f"0x{HOOK_RETURN_VA:08X}",
            "file_offset": f"0x{HOOK_OFF:08X}",
            "original": fmt(HOOK_ORIG),
            "patched": fmt(hpatch),
            "current": fmt(cur_hook),
        },
        "cave": {
            "file_offset": f"0x{cave_off:08X}",
            "va": f"0x{cave_va:08X}",
            "size": len(stub),
            "stub": fmt(stub),
            "original": fmt(bytes(data[cave_off:cave_off+len(stub)])),
        },
        "callback": {
            "va": f"0x{GARAGE_LISTENER_CALLBACK_VA:08X}",
            "this": "GS_Garage + 0x298",
            "status": 0,
            "context_object": 0,
            "context_control": 0,
            "abi_stack": "[return][status][context.object][context.control]",
        },
        "semantics": [
            "skip dead CraftCar backend request",
            "preserve client-created CraftCar operation",
            "let GS_Garage store operation and register listener",
            "run original GS virtual +0x54",
            "dispatch local status=0 through original garage listener",
            "continue original BuildCar cleanup",
        ],
        "aslr_safe": True,
        "can_apply": can,
    }
    if not can:
        report["error"] = "Prerequisite or target bytes are not in a known state."
    p = write_json(root, REPORT_REL, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n[REPORT] {p}")
    return 0 if can else 4


def apply(root: Path):
    exe, data = load(root)
    before_sha = sha256(data)
    image_base, sections = pe_sections(data)

    if bytes(data[R15_OFF:R15_OFF+len(R15_BYTES)]) != R15_BYTES:
        print("[ERRO] R15 nao esta aplicada. R16 exige R15.")
        return 5

    # If state exists and all bytes match it, treat as already applied.
    state_path = root / STATE_REL
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            cave_off = int(state["cave"]["file_offset"], 16)
            cave_va = int(state["cave"]["va"], 16)
            stub = bytes.fromhex(state["cave"]["stub"])
            hp = bytes.fromhex(state["completion_hook"]["patched"])
            if (
                bytes(data[NET_CALL_OFF:NET_CALL_OFF+5]) == NET_CALL_PATCH
                and bytes(data[HOOK_OFF:HOOK_OFF+HOOK_LEN]) == hp
                and bytes(data[cave_off:cave_off+len(stub)]) == stub
            ):
                print("[OK] R16 ja esta aplicada.")
                return 0
        except Exception:
            pass

    if bytes(data[NET_CALL_OFF:NET_CALL_OFF+5]) != NET_CALL_ORIG:
        print("[ERRO] CraftCar network call esta em estado desconhecido; nada alterado.")
        print("[ATUAL]", fmt(bytes(data[NET_CALL_OFF:NET_CALL_OFF+5])))
        return 6

    if bytes(data[HOOK_OFF:HOOK_OFF+HOOK_LEN]) != HOOK_ORIG:
        print("[ERRO] BuildCar completion hook esta em estado desconhecido; nada alterado.")
        print("[ATUAL]", fmt(bytes(data[HOOK_OFF:HOOK_OFF+HOOK_LEN])))
        return 7

    cave_off, cave_va = find_exec_cc_cave(data, image_base, sections)
    stub = build_stub(cave_va)
    hp = hook_bytes(cave_va)

    if bytes(data[cave_off:cave_off+len(stub)]) != b"\xCC"*len(stub):
        print("[ERRO] Cave deixou de estar livre; nada alterado.")
        return 8

    backup_dir = root / "_BACKUPS" / "R16"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"AMS.exe.{before_sha}.bak"
    if not backup.exists():
        shutil.copy2(exe, backup)

    # Transaction in memory, then one write.
    data[NET_CALL_OFF:NET_CALL_OFF+5] = NET_CALL_PATCH
    data[cave_off:cave_off+len(stub)] = stub
    data[HOOK_OFF:HOOK_OFF+HOOK_LEN] = hp
    exe.write_bytes(data)

    verify = exe.read_bytes()
    ok = (
        verify[NET_CALL_OFF:NET_CALL_OFF+5] == NET_CALL_PATCH
        and verify[HOOK_OFF:HOOK_OFF+HOOK_LEN] == hp
        and verify[cave_off:cave_off+len(stub)] == stub
    )
    if not ok:
        shutil.copy2(backup, exe)
        raise RuntimeError("R16 verification failed; backup restored")

    state = {
        "name": "R16 LocalCraft Runtime Bridge",
        "created_at": datetime.now().isoformat(),
        "sha256_before": before_sha,
        "sha256_after": sha256(verify),
        "backup": str(backup),
        "network_call": {
            "file_offset": f"0x{NET_CALL_OFF:08X}",
            "original": fmt(NET_CALL_ORIG),
            "patched": fmt(NET_CALL_PATCH),
        },
        "completion_hook": {
            "file_offset": f"0x{HOOK_OFF:08X}",
            "va": f"0x{HOOK_VA:08X}",
            "original": fmt(HOOK_ORIG),
            "patched": fmt(hp),
        },
        "cave": {
            "file_offset": f"0x{cave_off:08X}",
            "va": f"0x{cave_va:08X}",
            "stub": fmt(stub),
            "original": fmt(b"\xCC"*len(stub)),
            "size": len(stub),
        },
        "callback": {
            "va": f"0x{GARAGE_LISTENER_CALLBACK_VA:08X}",
            "status": 0,
            "context": [0, 0],
        },
        "result": "applied",
    }
    write_json(root, STATE_REL, state)
    rp = write_json(root, REPORT_REL, {**state, "action": "apply"})

    print("[OK] R16 aplicada.")
    print(f"[SHA256 BEFORE] {before_sha}")
    print(f"[SHA256 AFTER ] {state['sha256_after']}")
    print(f"[NET CALL] 0x{NET_CALL_OFF:08X}: {fmt(NET_CALL_ORIG)} -> {fmt(NET_CALL_PATCH)}")
    print(f"[HOOK]     0x{HOOK_OFF:08X}: {fmt(HOOK_ORIG)} -> {fmt(hp)}")
    print(f"[CAVE]     file=0x{cave_off:08X} va=0x{cave_va:08X} size={len(stub)}")
    print(f"[BACKUP]   {backup}")
    print(f"[REPORT]   {rp}")
    return 0


def revert(root: Path):
    exe, data = load(root)
    state_path = root / STATE_REL
    if not state_path.is_file():
        # Surgical fallback if only the two fixed sites need restoration is
        # unsafe without knowing the dynamically chosen cave.
        print(f"[ERRO] Estado R16 nao encontrado: {state_path}")
        print("Use o backup R16 correspondente se o state.json foi removido.")
        return 9

    state = json.loads(state_path.read_text(encoding="utf-8"))
    cave_off = int(state["cave"]["file_offset"], 16)
    stub = bytes.fromhex(state["cave"]["stub"])
    cave_orig = bytes.fromhex(state["cave"]["original"])
    hp = bytes.fromhex(state["completion_hook"]["patched"])

    cur_net = bytes(data[NET_CALL_OFF:NET_CALL_OFF+5])
    cur_hook = bytes(data[HOOK_OFF:HOOK_OFF+HOOK_LEN])
    cur_cave = bytes(data[cave_off:cave_off+len(stub)])

    if cur_net == NET_CALL_ORIG and cur_hook == HOOK_ORIG and cur_cave == cave_orig:
        print("[OK] R16 ja esta revertida.")
        return 0

    if cur_net != NET_CALL_PATCH or cur_hook != hp or cur_cave != stub:
        print("[ERRO] Bytes R16 nao correspondem ao state.json; revert recusado.")
        print("[NET ]", fmt(cur_net))
        print("[HOOK]", fmt(cur_hook))
        return 10

    before = sha256(data)
    pre_dir = root / "_BACKUPS" / "R16"
    pre_dir.mkdir(parents=True, exist_ok=True)
    pre = pre_dir / f"AMS.exe.pre-revert.{before}.bak"
    if not pre.exists():
        shutil.copy2(exe, pre)

    data[NET_CALL_OFF:NET_CALL_OFF+5] = NET_CALL_ORIG
    data[HOOK_OFF:HOOK_OFF+HOOK_LEN] = HOOK_ORIG
    data[cave_off:cave_off+len(cave_orig)] = cave_orig
    exe.write_bytes(data)

    verify = exe.read_bytes()
    ok = (
        verify[NET_CALL_OFF:NET_CALL_OFF+5] == NET_CALL_ORIG
        and verify[HOOK_OFF:HOOK_OFF+HOOK_LEN] == HOOK_ORIG
        and verify[cave_off:cave_off+len(cave_orig)] == cave_orig
    )
    if not ok:
        shutil.copy2(pre, exe)
        raise RuntimeError("R16 revert verification failed; pre-revert backup restored")

    report = {
        "name": "R16 LocalCraft Runtime Bridge",
        "action": "revert",
        "result": "reverted",
        "created_at": datetime.now().isoformat(),
        "sha256_before": before,
        "sha256_after": sha256(verify),
        "pre_revert_backup": str(pre),
    }
    rp = write_json(root, REPORT_REL, report)
    print("[OK] R16 revertida.")
    print(f"[SHA256] {report['sha256_after']}")
    print(f"[REPORT] {rp}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--revert", action="store_true")
    ns = ap.parse_args()
    root = Path(ns.project_root).resolve()

    if ns.plan:
        return plan(root)
    if ns.apply:
        return apply(root)
    return revert(root)


if __name__ == "__main__":
    raise SystemExit(main())
