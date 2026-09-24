from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "audit_replay_transform_bindings.py"
spec = importlib.util.spec_from_file_location("audit_replay_transform_bindings", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def row(va: int, base: str, disp: int):
    return mod.MemoryAccess(
        va=va,
        size=4,
        mnemonic="movss",
        op_str=f"xmm0, dword ptr [{base} + {disp}]",
        base=base,
        index=None,
        scale=1,
        displacement=disp,
        access="read",
        instruction_bytes="F3 0F 10 00",
    )


def test_cluster_detects_xyz():
    rows = [
        row(0x401000, "esi", 0x30),
        row(0x401006, "esi", 0x34),
        row(0x40100C, "esi", 0x38),
    ]
    clusters = mod.cluster_accesses(rows)
    assert clusters
    assert clusters[0]["kind"] == "vector3"
    assert clusters[0]["base_register"] == "esi"


def test_cluster_detects_quaternion_shape():
    rows = [
        row(0x401000, "edi", 0x40),
        row(0x401005, "edi", 0x44),
        row(0x40100A, "edi", 0x48),
        row(0x40100F, "edi", 0x4C),
    ]
    clusters = mod.cluster_accesses(rows)
    assert clusters[0]["kind"] == "quaternion-or-vector4"
    assert len(clusters[0]["displacements"]) == 4
