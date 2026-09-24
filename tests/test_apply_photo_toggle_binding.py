from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
MODULE = TOOLS / "apply_photo_toggle_binding.py"

spec = importlib.util.spec_from_file_location("apply_photo_toggle_binding", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_registry_is_fail_closed(tmp_path: Path):
    path = tmp_path / "binding.json"
    path.write_text(json.dumps({
        "format": "rextreme-photo-toggle-binding",
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
        raise AssertionError("disabled Photo toggle binding was accepted")


def test_toggle_selector_is_embedded():
    binding = {
        "cave_va": 0x00404000,
        "cave_length": 64,
        "expected": bytes.fromhex("8B C1 8B 40 04"),
        "this_register": "ecx",
        "resume_va": 0x00401005,
    }
    stub = mod.build_stub(binding)
    assert bytes.fromhex("68 04 B0 DE C0") in stub
    assert len(stub) == 64
