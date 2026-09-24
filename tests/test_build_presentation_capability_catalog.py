from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "build_presentation_capability_catalog.py"
spec = importlib.util.spec_from_file_location("build_presentation_capability_catalog", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def write_source(path: Path, capabilities: list[dict]) -> None:
    path.write_text(json.dumps({
        "format": "rextreme-presentation-capabilities",
        "version": 1,
        "build": "1.7.3.8-x86",
        "capabilities": capabilities,
    }), encoding="utf-8")


def test_empty_catalog_is_valid(tmp_path: Path):
    src = tmp_path / "caps.json"
    out = tmp_path / "CampaignPresentationOptions.dat"
    write_source(src, [])
    result = mod.build(src, out)
    assert result["count"] == 0
    assert result["safe_empty_catalog"] is True
    assert len(out.read_bytes()) == mod.HEADER.size


def test_unverified_capability_is_rejected(tmp_path: Path):
    src = tmp_path / "caps.json"
    out = tmp_path / "out.dat"
    write_source(src, [{
        "id": "fov",
        "kind": "slider",
        "minimum": 50,
        "maximum": 100,
        "step": 1,
        "original_value": 70,
        "verified": False,
        "evidence": [{"file": "AMS.exe", "rva": 123}],
    }])
    try:
        mod.build(src, out)
    except mod.CatalogError as exc:
        assert "verified" in str(exc)
    else:
        raise AssertionError("unverified capability was accepted")


def test_verified_capability_requires_evidence(tmp_path: Path):
    src = tmp_path / "caps.json"
    out = tmp_path / "out.dat"
    write_source(src, [{
        "id": "fov",
        "kind": "slider",
        "minimum": 50,
        "maximum": 100,
        "step": 1,
        "original_value": 70,
        "verified": True,
        "evidence": [],
    }])
    try:
        mod.build(src, out)
    except mod.CatalogError as exc:
        assert "evidence" in str(exc)
    else:
        raise AssertionError("capability without evidence was accepted")
