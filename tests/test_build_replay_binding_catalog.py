from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "build_replay_binding_catalog.py"
spec = importlib.util.spec_from_file_location("build_replay_binding_catalog", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def write_source(path: Path, bindings: list[dict], pe=None):
    path.write_text(json.dumps({
        "format": "rextreme-replay-bindings",
        "version": 1,
        "build": "1.7.3.8-x86",
        "pe": pe,
        "bindings": bindings,
    }), encoding="utf-8")


def test_empty_catalog_is_safe(tmp_path: Path):
    src = tmp_path / "replay.json"
    out = tmp_path / "CampaignReplayBindings.dat"
    write_source(src, [])
    summary = mod.build(src, out)
    assert summary["count"] == 0
    assert summary["safe_empty_catalog"] is True
    assert summary["recording_ready"] is False
    assert len(out.read_bytes()) == mod.HEADER.size


def test_nonempty_requires_pe_fingerprint(tmp_path: Path):
    src = tmp_path / "replay.json"
    out = tmp_path / "out.dat"
    write_source(src, [{
        "semantic": "time_ms",
        "root": "gui_argument",
        "chain": [16],
        "field_offset": 8,
        "value_kind": "u32",
        "scale_divisor": 1,
        "verified": True,
        "evidence": [{"source": "disassembly"}],
    }])
    try:
        mod.build(src, out)
    except mod.BindingError as exc:
        assert "pe fingerprint" in str(exc)
    else:
        raise AssertionError("missing PE fingerprint was accepted")


def test_required_semantic_cannot_be_optional(tmp_path: Path):
    src = tmp_path / "replay.json"
    out = tmp_path / "out.dat"
    write_source(src, [{
        "semantic": "position_x",
        "root": "gui_argument",
        "chain": [],
        "field_offset": 32,
        "value_kind": "float_scaled",
        "scale_divisor": 1000,
        "optional": True,
        "verified": True,
        "evidence": [{"source": "disassembly"}],
    }], {"time_date_stamp": 1, "size_of_image": 2})
    try:
        mod.build(src, out)
    except mod.BindingError as exc:
        assert "cannot be optional" in str(exc)
    else:
        raise AssertionError("required semantic was accepted as optional")
