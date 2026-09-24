from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "build_photo_binding_catalog.py"
spec = importlib.util.spec_from_file_location("build_photo_binding_catalog", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def write_source(path: Path, bindings: list[dict]) -> None:
    path.write_text(json.dumps({
        "format": "rextreme-photo-bindings",
        "version": 1,
        "build": "1.7.3.8-x86",
        "bindings": bindings,
    }), encoding="utf-8")


def bind(semantic: str, value_kind: str = "i32") -> dict:
    return {
        "semantic": semantic,
        "base_kind": "module_rva",
        "target_rva": "0x1234",
        "field_offset": 0,
        "value_kind": value_kind,
        "scale_divisor": 1000 if value_kind == "float_scaled" else 1,
        "verified": True,
        "evidence": [{"source": "AMS.exe", "note": "test"}],
    }


def test_empty_catalog_is_safe(tmp_path: Path):
    src = tmp_path / "photo.json"
    out = tmp_path / "CampaignPhotoBindings.dat"
    write_source(src, [])
    result = mod.build(src, out)
    assert result["count"] == 0
    assert result["free_camera_ready"] is False
    assert result["safe_empty_catalog"] is True
    assert len(out.read_bytes()) == mod.HEADER.size


def test_free_camera_requires_complete_semantics(tmp_path: Path):
    src = tmp_path / "photo.json"
    out = tmp_path / "out.dat"
    bindings = [
        bind("position_x", "float_scaled"),
        bind("position_y", "float_scaled"),
        bind("position_z", "float_scaled"),
        bind("pitch"),
        bind("yaw"),
        bind("roll"),
        bind("hud_visible", "u8_bool"),
    ]
    write_source(src, bindings)
    result = mod.build(src, out)
    assert result["count"] == 7
    assert result["free_camera_ready"] is True


def test_hud_must_be_boolean(tmp_path: Path):
    src = tmp_path / "photo.json"
    out = tmp_path / "out.dat"
    write_source(src, [bind("hud_visible", "i32")])
    try:
        mod.build(src, out)
    except mod.PhotoBindingError as exc:
        assert "u8_bool" in str(exc)
    else:
        raise AssertionError("invalid HUD binding was accepted")


def test_unverified_binding_rejected(tmp_path: Path):
    src = tmp_path / "photo.json"
    out = tmp_path / "out.dat"
    row = bind("pitch")
    row["verified"] = False
    write_source(src, [row])
    try:
        mod.build(src, out)
    except mod.PhotoBindingError as exc:
        assert "verified" in str(exc)
    else:
        raise AssertionError("unverified Photo binding was accepted")
