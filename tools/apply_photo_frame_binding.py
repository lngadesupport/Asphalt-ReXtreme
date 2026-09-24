#!/usr/bin/env python3
"""Apply a verified Photo Mode per-frame hook to AMS.exe.

This mirrors the Replay frame safety model but targets selector 0xC0DEB003.
It is intentionally fail-closed until exact 1.7.3.8 evidence exists.
"""
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
PHOTO_FRAME_MAGIC = 0xC0DEB003

REG_TO_ECX = {
    "ecx": b"",
    "eax": b"\x8B\xC8",
    "ebx": b"\x8B\xCB",
    "edx": b"\x8B\xCA",
    "esi": b"\x8B\xCE",
    "edi": b"\x8B\xCF",
}


class BindingError(RuntimeError):
    pass


def rel32(src_va: int, instruction_len: int, dst_va: int) -> bytes:
    delta = dst_va - (src_va + instruction_len)
    if not (-0x80000000 <= delta <= 0x7FFFFFFF):
        raise BindingError("rel32 target out of range")
    return struct.pack("<i", delta)


def parse_int(value, name: str) -> int:
    if isinstance(value, bool):
        raise BindingError(f"{name}: bool is not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise BindingError(f"{name}: invalid integer {value!r}") from exc
    raise BindingError(f"{name}: expected integer or 0x string")


def parse_hex(value: str, name: str) -> bytes:
    if not isinstance(value, str) or not value.strip():
        raise BindingError(f"{name}: expected non-empty hex string")
    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise BindingError(f"{name}: invalid hex") from exc


def validate_pe32_x86(data: bytes) -> None:
    if len(data) < 0x100 or data[:2] != b"MZ":
        raise BindingError("AMS.exe is not MZ")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 0x18 >= len(data) or data[pe:pe + 4] != b"PE\0\0":
        raise BindingError("invalid PE signature")
    if struct.unpack_from("<H", data, pe + 4)[0] != 0x014C:
        raise BindingError("expected x86 PE")
    opt = pe + 24
    if struct.unpack_from("<H", data, opt)[0] != 0x010B:
        raise BindingError("expected PE32")
    if struct.unpack_from("<I", data, opt + 28)[0] != IMAGE_BASE:
        raise BindingError("unexpected image base")


def validate_relocatable_original(original: bytes, site_va: int) -> None:
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32  # type: ignore
    except ImportError as exc:
        raise BindingError("capstone is required") from exc

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    consumed = 0
    for ins in md.disasm(original, site_va):
        consumed += ins.size
        mnemonic = ins.mnemonic.lower()
        if mnemonic.startswith("j") or mnemonic.startswith("loop") or mnemonic == "call":
            raise BindingError(
                f"unsafe relocated control-flow instruction {mnemonic} at 0x{ins.address:08X}"
            )
    if consumed != len(original):
        raise BindingError("expected_hex does not end on an instruction boundary")


def load_binding(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "rextreme-photo-frame-binding":
        raise BindingError("invalid binding format")
    if data.get("version") != 1 or data.get("build") != "1.7.3.8-x86":
        raise BindingError("binding must target 1.7.3.8-x86 version 1")
    if data.get("enabled") is not True:
        raise BindingError("no verified Photo Mode frame binding is enabled")
    b = data.get("binding")
    if not isinstance(b, dict):
        raise BindingError("binding object missing")
    if b.get("verified") is not True:
        raise BindingError("binding.verified must be true")
    evidence = b.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise BindingError("binding requires non-empty evidence")
    return b


def normalize(raw: dict) -> dict:
    site_va = parse_int(raw.get("site_va"), "site_va")
    site_off = parse_int(raw.get("site_file_offset"), "site_file_offset")
    resume_va = parse_int(raw.get("resume_va"), "resume_va")
    cave_va = parse_int(raw.get("cave_va"), "cave_va")
    cave_off = parse_int(raw.get("cave_file_offset"), "cave_file_offset")
    cave_len = parse_int(raw.get("cave_length"), "cave_length")
    original = parse_hex(raw.get("expected_hex"), "expected_hex")
    cave_fill = parse_hex(raw.get("cave_expected_hex", "CC"), "cave_expected_hex")
    this_register = str(raw.get("this_register", "")).lower()

    if len(original) < 5:
        raise BindingError("expected_hex must cover at least 5 bytes")
    if cave_len < 32 or cave_len > 512:
        raise BindingError("cave_length must be 32..512")
    if len(cave_fill) not in (1, cave_len):
        raise BindingError("cave_expected_hex must be one byte or exactly cave_length bytes")
    if this_register not in REG_TO_ECX:
        raise BindingError(f"unsupported this_register {this_register!r}")
    if resume_va != site_va + len(original):
        raise BindingError("resume_va must equal site_va + expected length")
    validate_relocatable_original(original, site_va)

    return {
        **raw,
        "site_va": site_va,
        "site_file_offset": site_off,
        "resume_va": resume_va,
        "cave_va": cave_va,
        "cave_file_offset": cave_off,
        "cave_length": cave_len,
        "expected": original,
        "cave_fill": cave_fill,
        "this_register": this_register,
    }


def pic_gateway_call(cave_va: int, prefix_len: int) -> bytes:
    code = bytearray()
    code += b"\x68" + struct.pack("<I", PHOTO_FRAME_MAGIC)
    code += b"\xE8\x00\x00\x00\x00"
    code += b"\x58"
    pop_next = cave_va + prefix_len + len(code)
    code += b"\x05" + struct.pack("<I", (IGP_HTTPPOST_PREF_VA - pop_next) & 0xFFFFFFFF)
    code += b"\xFF\x10"
    return bytes(code)


def build_stub(binding: dict) -> bytes:
    code = bytearray()
    code += b"\x9C\x60"
    code += REG_TO_ECX[binding["this_register"]]
    code += pic_gateway_call(binding["cave_va"], len(code))
    code += b"\x61\x9D"
    code += binding["expected"]
    jmp_va = binding["cave_va"] + len(code)
    code += b"\xE9" + rel32(jmp_va, 5, binding["resume_va"])

    if len(code) > binding["cave_length"]:
        raise BindingError("generated stub exceeds verified cave")
    return bytes(code) + b"\xCC" * (binding["cave_length"] - len(code))


def site_patch(binding: dict) -> bytes:
    patch = b"\xE9" + rel32(binding["site_va"], 5, binding["cave_va"])
    return patch + b"\x90" * (len(binding["expected"]) - 5)


def expected_cave(binding: dict) -> bytes:
    fill = binding["cave_fill"]
    return fill * binding["cave_length"] if len(fill) == 1 else fill


def require(data: bytes, off: int, expected: bytes, name: str) -> None:
    got = data[off:off + len(expected)]
    if got != expected:
        raise BindingError(
            f"{name}: bytes mismatch at 0x{off:08X}: "
            f"expected [{expected.hex(' ').upper()}], got [{got.hex(' ').upper()}]"
        )


def apply(ams: Path, binding_path: Path, project_root: Path, check_only: bool) -> dict:
    raw = load_binding(binding_path)
    b = normalize(raw)
    data = bytearray(ams.read_bytes())
    validate_pe32_x86(data)

    stub = build_stub(b)
    patch = site_patch(b)
    require(data, b["site_file_offset"], b["expected"], "Photo frame hook site")
    require(data, b["cave_file_offset"], expected_cave(b), "Photo frame cave")

    before = hashlib.sha256(data).hexdigest()
    report = {
        "format": "rextreme-photo-frame-binding-apply",
        "version": 1,
        "build": "1.7.3.8-x86",
        "selector": f"0x{PHOTO_FRAME_MAGIC:08X}",
        "site_va": f"0x{b['site_va']:08X}",
        "cave_va": f"0x{b['cave_va']:08X}",
        "this_register": b["this_register"],
        "evidence": raw["evidence"],
        "check_only": check_only,
        "applied": False,
        "sha256_before": before,
        "sha256_after": before,
    }

    if check_only:
        return report

    backup_dir = project_root / "_BACKUPS" / "PHOTO-FRAME-BINDING"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"AMS.{before}.bak"
    if not backup.exists():
        shutil.copy2(ams, backup)

    data[b["cave_file_offset"]:b["cave_file_offset"] + b["cave_length"]] = stub
    data[b["site_file_offset"]:b["site_file_offset"] + len(patch)] = patch

    tmp = ams.with_suffix(".photo-frame.tmp")
    tmp.write_bytes(data)
    verify = tmp.read_bytes()
    require(verify, b["site_file_offset"], patch, "Photo frame redirect verification")
    require(verify, b["cave_file_offset"], stub, "Photo frame stub verification")
    tmp.replace(ams)

    report["applied"] = True
    report["backup"] = str(backup)
    report["sha256_after"] = hashlib.sha256(ams.read_bytes()).hexdigest()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply verified ReXtreme Photo Mode per-frame AMS binding")
    ap.add_argument("ams", type=Path)
    ap.add_argument("--binding", type=Path, default=Path("config/photo-frame-binding.verified.json"))
    ap.add_argument("--project-root", type=Path, default=Path("."))
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--report", type=Path, default=Path("_TRACE_MONTAR/PHOTO-FRAME-BINDING.json"))
    ns = ap.parse_args()

    try:
        report = apply(ns.ams.resolve(), ns.binding.resolve(), ns.project_root.resolve(), ns.check_only)
    except (OSError, json.JSONDecodeError, BindingError) as exc:
        print(f"[ERRO] {exc}")
        return 1

    ns.report.parent.mkdir(parents=True, exist_ok=True)
    ns.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] wrote {ns.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
