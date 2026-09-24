from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "audit_presentation_capabilities.py"
spec = importlib.util.spec_from_file_location("audit_presentation_capabilities", MODULE_PATH)
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def test_ascii_string_extraction():
    data = b"\x00hello\x00FOV=75\x00shadow_quality=2\x00"
    values = list(audit.iter_ascii_strings(data))
    texts = [x[1] for x in values]
    assert "hello" in texts
    assert "FOV=75" in texts
    assert "shadow_quality=2" in texts


def test_utf16_string_extraction():
    data = b"\x00\x00" + "camera_distance".encode("utf-16le") + b"\x00\x00"
    values = list(audit.iter_utf16le_strings(data))
    assert any(text == "camera_distance" for _, text in values)


def test_classification_is_candidate_only():
    matches = audit.classify("Motion_Blur Camera_Distance Replay")
    assert ("quality", "motion_blur") in matches
    assert ("camera", "camera_distance") in matches
    assert ("replay_photo", "replay") in matches


def test_raw_to_rva():
    section = audit.Section(".rdata", 0x2000, 0x1000, 0x400, 0x800)
    assert audit.raw_to_rva(0x450, [section]) == 0x2050
    assert audit.raw_to_rva(0x100, [section]) is None
