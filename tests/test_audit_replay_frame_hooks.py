from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
MODULE = TOOLS / "audit_replay_frame_hooks.py"

spec = importlib.util.spec_from_file_location("audit_replay_frame_hooks", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_undecorate_simple_class():
    assert mod.undecorate_simple(".?AVGameModeGUIBase@@") == "GameModeGUIBase"


def test_undecorate_simple_namespace():
    assert mod.undecorate_simple(".?AVCamera@Gameplay@@") == "Gameplay::Camera"


def test_score_prefers_game_mode_float_update_shape():
    method = {
        "instruction_count": 42,
        "call_count": 5,
        "branch_count": 4,
        "refs_game_mode_field_0x14": 2,
        "scalar_float_ops": 3,
        "ret_seen": True,
    }
    score, reasons = mod.score_method(method, 0x20, [0x00401000])
    assert score >= 10
    assert any("GameModeGUIBase+0x14" in reason for reason in reasons)
    assert any("float" in reason for reason in reasons)


def test_anchor_verification():
    data = b"\x00" * 16 + b"\x8B\xC3\x8B\x4D\xF4" + b"\x00" * 4
    row = mod.verify_anchor(data, 16, bytes.fromhex("8B C3 8B 4D F4"), "begin")
    assert row["matches"] is True
