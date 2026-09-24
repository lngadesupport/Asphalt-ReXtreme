from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
MODULE = TOOLS / "audit_original_ui_rtti.py"
spec = importlib.util.spec_from_file_location("audit_original_ui_rtti", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_ui_rtti_name_scores():
    score, hits = mod.class_score(".?AVGameSettingsMenuGUI@@")
    assert score > 0
    assert "gui" in hits
    assert "menu" in hits
    assert "setting" in hits


def test_unrelated_rtti_name_is_ignored():
    score, hits = mod.class_score(".?AVVehiclePhysicsController@@")
    assert score == 0
    assert hits == []
