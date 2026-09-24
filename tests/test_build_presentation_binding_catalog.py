from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "build_presentation_binding_catalog.py"
spec = importlib.util.spec_from_file_location("build_presentation_binding_catalog", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def write_caps(path: Path, caps: list[dict]) -> None:
    path.write_text(json.dumps({
        "format": "rextreme-presentation-capabilities",
        "version": mod.VERSION,
        "build": "1.7.3.8-x86",
        "capabilities": caps,
    }), encoding="utf-8")


def write_bindings(path: Path, bindings: list[dict]) -> None:
    path.write_text(json.dumps({
        "format": "rextreme-presentation-bindings",
        "version": 1,
        "build": "1.7.3.8-x86",
        "bindings": bindings,
    }), encoding="utf-8")


def verified_fov_cap() -> dict:
    return {
        "id": "fov",
        "kind": "slider",
        "minimum": 5000,
        "maximum": 10000,
        "step": 100,
        "original_value": 7000,
        "verified": True,
        "evidence": [{"source": "AMS.exe", "note": "test"}],
    }


def test_empty_binding_catalog_is_valid(tmp_path: Path):
    caps = tmp_path / "caps.json"
    src = tmp_path / "bindings.json"
    out = tmp_path / "CampaignPresentationBindings.dat"
    write_caps(caps, [])
    write_bindings(src, [])
    result = mod.build(src, caps, out)
    assert result["count"] == 0
    assert result["safe_empty_catalog"] is True
    assert len(out.read_bytes()) == mod.HEADER.size


def test_binding_requires_verified_capability(tmp_path: Path):
    caps = tmp_path / "caps.json"
    src = tmp_path / "bindings.json"
    out = tmp_path / "out.dat"
    write_caps(caps, [])
    write_bindings(src, [{
        "id": "fov",
        "base_kind": "module_rva",
        "target_rva": "0x1234",
        "field_offset": 0,
        "value_kind": "i32",
        "scale_divisor": 1,
        "verified": True,
        "evidence": [{"source": "AMS.exe"}],
    }])
    try:
        mod.build(src, caps, out)
    except mod.BindingCatalogError as exc:
        assert "no verified capability" in str(exc)
    else:
        raise AssertionError("orphan binding was accepted")


def test_verified_binding_builds(tmp_path: Path):
    caps = tmp_path / "caps.json"
    src = tmp_path / "bindings.json"
    out = tmp_path / "out.dat"
    write_caps(caps, [verified_fov_cap()])
    write_bindings(src, [{
        "id": "fov",
        "base_kind": "pointer_rva",
        "target_rva": "0x0153AC20",
        "field_offset": 16,
        "value_kind": "float_scaled",
        "scale_divisor": 100,
        "verified": True,
        "evidence": [{"source": "AMS.exe", "rva": "0x0153AC20"}],
    }], target_pe={"time_date_stamp": "0x12345678", "size_of_image": "0x02000000"})
    result = mod.build(src, caps, out)
    assert result["count"] == 1
    assert result["binding_ids"] == ["fov"]
    assert len(out.read_bytes()) == mod.HEADER.size + mod.ENTRY.size


def test_unverified_binding_rejected(tmp_path: Path):
    caps = tmp_path / "caps.json"
    src = tmp_path / "bindings.json"
    out = tmp_path / "out.dat"
    write_caps(caps, [verified_fov_cap()])
    write_bindings(src, [{
        "id": "fov",
        "base_kind": "module_rva",
        "target_rva": 0x1234,
        "field_offset": 0,
        "value_kind": "i32",
        "scale_divisor": 1,
        "verified": False,
        "evidence": [{"source": "AMS.exe"}],
    }])
    try:
        mod.build(src, caps, out)
    except mod.BindingCatalogError as exc:
        assert "verified" in str(exc)
    else:
        raise AssertionError("unverified binding was accepted")
