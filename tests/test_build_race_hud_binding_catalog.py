from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "tools" / "build_race_hud_binding_catalog.py"
spec = importlib.util.spec_from_file_location("build_race_hud_binding_catalog", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def write(path: Path, bindings=None, policy=None, pe=None):
    path.write_text(json.dumps({
        "format": "rextreme-race-hud-bindings",
        "version": 1,
        "build": "1.7.3.8-x86",
        "policy": policy or {
            "original_elements_only": True,
            "create_new_hud_widgets": False,
        },
        "pe": pe,
        "bindings": bindings or [],
    }), encoding="utf-8")


def test_layout_matches_runtime_struct():
    assert mod.HEADER.size == 28
    assert mod.ENTRY.size == 32


def test_empty_catalog_is_safe(tmp_path: Path):
    src = tmp_path / "hud.json"
    out = tmp_path / "CampaignRaceHudBindings.dat"
    write(src)
    result = mod.build(src, out)
    assert result["count"] == 0
    assert result["safe_empty_catalog"]
    assert result["original_elements_only"]
    assert result["create_new_hud_widgets"] is False


def test_cannot_enable_new_widgets(tmp_path: Path):
    src = tmp_path / "hud.json"
    out = tmp_path / "out.dat"
    write(src, policy={
        "original_elements_only": True,
        "create_new_hud_widgets": True,
    })
    try:
        mod.build(src, out)
    except mod.BindingError as exc:
        assert "create_new_hud_widgets" in str(exc)
    else:
        raise AssertionError("new HUD widget policy was accepted")


def test_binding_requires_evidence_and_pe(tmp_path: Path):
    src = tmp_path / "hud.json"
    out = tmp_path / "out.dat"
    write(src, bindings=[{
        "element": "speed",
        "property": "x",
        "base": "module_rva",
        "target_rva": "0x1000",
        "field_offset": 0,
        "value_kind": "float_scaled",
        "scale_divisor": 1000,
        "verified": True,
        "evidence": [{"source": "runtime trace"}],
    }])
    try:
        mod.build(src, out)
    except mod.BindingError as exc:
        assert "PE fingerprint" in str(exc)
    else:
        raise AssertionError("non-empty HUD catalog without PE fingerprint was accepted")


def test_gui_argument_binding_uses_zero_rva(tmp_path: Path):
    src = tmp_path / "hud.json"
    out = tmp_path / "out.dat"
    write(src, bindings=[{
        "element": "nitro",
        "property": "x",
        "base": "gui_argument",
        "target_rva": 0,
        "field_offset": 4,
        "value_kind": "float_scaled",
        "scale_divisor": 1000,
        "verified": True,
        "evidence": [{"source": "verified GameModeGUIBase field"}],
    }], pe={"time_date_stamp": 1, "size_of_image": 2})
    result = mod.build(src, out)
    assert result["count"] == 1
    assert len(out.read_bytes()) == mod.HEADER.size + mod.ENTRY.size
