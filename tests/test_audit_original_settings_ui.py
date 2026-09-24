from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
MODULE_PATH = TOOLS / "audit_original_settings_ui.py"
spec = importlib.util.spec_from_file_location("audit_original_settings_ui", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_keyword_hits():
    hits = mod.keyword_hits("GS_Settings_Graphics_Slider")
    assert "settings" in hits
    assert "graphics" in hits
    assert "slider" in hits


def test_blob_scan_marks_candidates():
    rows = mod.scan_blob(b"foo\x00VIDEO_SETTINGS_SLIDER\x00bar", "AMS.exe")
    assert rows
    assert all(row["status"] == "candidate-only" for row in rows)
    assert all("xref_count" in row for row in rows)
    assert all(row["xref_count"] == 0 for row in rows)
