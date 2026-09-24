from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "tools" / "rank_original_ui_candidates.py"
spec = importlib.util.spec_from_file_location("rank_original_ui_candidates", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_xrefs_raise_candidate_priority():
    base = {
        "text": "graphics settings slider",
        "source": "AMS.exe",
        "keywords": ["graphics", "settings", "slider"],
        "rva": 0x1234,
        "va": 0x401234,
        "encoding": "ascii",
    }
    low = dict(base, xref_count=0)
    high = dict(base, xref_count=5)
    low_score, _ = mod.score_candidate("ui.slider", low)
    high_score, _ = mod.score_candidate("ui.slider", high)
    assert high_score > low_score


def test_ranking_never_marks_verified():
    report = {
        "format": "rextreme-original-settings-ui-audit",
        "candidates": [{
            "text": "PauseMenu Button",
            "source": "AMS.exe",
            "keywords": ["pause", "menu", "button"],
            "rva": 1,
            "va": 2,
            "xref_count": 3,
            "xref_rvas": [10, 20, 30],
            "encoding": "ascii",
            "offset": 100,
        }],
    }
    output = mod.rank(report, 5)
    found = [
        c
        for role in output["roles"].values()
        for c in role["candidates"]
    ]
    assert found
    assert all(c["verified"] is False for c in found)
    assert all(c["status"] == "candidate-only" for c in found)
