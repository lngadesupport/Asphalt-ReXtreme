from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
MODULE = TOOLS / "audit_race_hud_fields.py"
spec = importlib.util.spec_from_file_location("audit_race_hud_fields", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

from audit_replay_transform_bindings import MemoryAccess


def access(va, base, disp, mnemonic="movss", mode="read"):
    return MemoryAccess(
        va=va, size=5, mnemonic=mnemonic,
        op_str=f"xmm0, [{base}+{disp}]",
        base=base, index=None, scale=1,
        displacement=disp, access=mode,
        instruction_bytes="00",
    )


def test_writable_float_field_ranks_above_single_read():
    rows = [
        access(0x401000, "esi", 0x20, "movss", "read"),
        access(0x401010, "esi", 0x20, "movss", "write"),
        access(0x401020, "esi", 0x20, "mulss", "read"),
        access(0x401030, "edi", 0x10, "mov", "read"),
    ]
    ranked = mod.rank_fields(rows)
    assert ranked[0].base_register == "esi"
    assert ranked[0].displacement == 0x20
    assert ranked[0].write_count == 1


def test_adjacent_float_fields_form_group():
    fields = mod.rank_fields([
        access(0x401000, "ecx", 0x30),
        access(0x401010, "ecx", 0x34),
        access(0x401020, "ecx", 0x38),
    ])
    groups = mod.neighbor_groups(fields)
    assert groups
    assert groups[0]["shape"] == "adjacent-float-style"
    assert all(g["status"] == "candidate-only" for g in groups)
