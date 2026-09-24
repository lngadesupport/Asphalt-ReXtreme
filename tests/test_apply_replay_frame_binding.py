from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
MODULE = TOOLS / "apply_replay_frame_binding.py"

spec = importlib.util.spec_from_file_location("apply_replay_frame_binding", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_registry_is_fail_closed(tmp_path: Path):
    path = tmp_path / "binding.json"
    path.write_text(json.dumps({
        "format": "rextreme-replay-frame-binding",
        "version": 1,
        "build": "1.7.3.8-x86",
        "enabled": False,
        "binding": None,
    }), encoding="utf-8")

    try:
        mod.load_binding(path)
    except mod.BindingError as exc:
        assert "no verified" in str(exc)
    else:
        raise AssertionError("disabled binding registry was accepted")


def test_site_patch_is_jump_plus_nops():
    binding = {
        "site_va": 0x00401000,
        "cave_va": 0x00402000,
        "expected": bytes.fromhex("8B C1 8B 40 04 85 C0"),
    }
    patch = mod.site_patch(binding)
    assert patch[0] == 0xE9
    assert len(patch) == len(binding["expected"])
    assert patch[-2:] == b"\x90\x90"


def test_stub_preserves_original_bytes_and_selector():
    binding = {
        "cave_va": 0x00402000,
        "cave_length": 64,
        "expected": bytes.fromhex("8B C1 8B 40 04"),
        "this_register": "esi",
        "resume_va": 0x00401005,
    }
    stub = mod.build_stub(binding)
    assert len(stub) == 64
    assert bytes.fromhex("68 02 B0 DE C0") in stub
    assert binding["expected"] in stub
    assert stub.endswith(b"\xCC")
