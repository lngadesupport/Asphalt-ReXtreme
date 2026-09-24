from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "tools" / "build_original_ui_binding_catalog.py"
spec = importlib.util.spec_from_file_location("build_original_ui_binding_catalog", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def source(path: Path, policy=None, bindings=None):
    path.write_text(json.dumps({
        "format": "rextreme-original-ui-bindings",
        "version": 1,
        "build": "1.7.3.8-x86",
        "policy": policy or {
            "original_ui_only": True,
            "custom_ui_assets_allowed": False,
            "fallback_if_unmapped": "feature-hidden",
        },
        "bindings": bindings or [],
    }), encoding="utf-8")


def test_empty_original_ui_catalog_is_safe(tmp_path: Path):
    src = tmp_path / "ui.json"
    out = tmp_path / "CampaignOriginalUiBindings.dat"
    source(src)
    result = mod.build(src, out)
    assert result["count"] == 0
    assert result["safe_empty_catalog"] is True
    assert result["original_ui_only"] is True
    assert result["custom_ui_assets_allowed"] is False
    assert len(out.read_bytes()) == mod.HEADER.size


def test_policy_cannot_enable_custom_ui(tmp_path: Path):
    src = tmp_path / "ui.json"
    out = tmp_path / "out.dat"
    source(src, {
        "original_ui_only": True,
        "custom_ui_assets_allowed": True,
        "fallback_if_unmapped": "feature-hidden",
    })
    try:
        mod.build(src, out)
    except mod.BindingError as exc:
        assert "custom_ui_assets_allowed" in str(exc)
    else:
        raise AssertionError("custom UI policy was accepted")


def test_unverified_binding_is_rejected(tmp_path: Path):
    src = tmp_path / "ui.json"
    out = tmp_path / "out.dat"
    source(src, bindings=[{
        "id": "photo.pause.entry",
        "kind": "button",
        "base": "module_rva",
        "target_rva": "0x1234",
        "field_offset": 0,
        "semantic": 1,
        "verified": False,
        "evidence": [{"source": "guess"}],
    }])
    try:
        mod.build(src, out)
    except mod.BindingError as exc:
        assert "verified" in str(exc)
    else:
        raise AssertionError("unverified UI binding was accepted")
