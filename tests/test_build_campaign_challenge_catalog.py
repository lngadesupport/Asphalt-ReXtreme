from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "tools" / "build_campaign_challenge_catalog.py"
spec = importlib.util.spec_from_file_location("build_campaign_challenge_catalog", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_empty_catalog_has_fixed_runtime_size(tmp_path: Path):
    src = tmp_path / "challenges.json"
    out = tmp_path / "CampaignChallenges.dat"
    src.write_text(json.dumps({
        "format": "rextreme-campaign-challenges",
        "version": 1,
        "challenges": [],
    }), encoding="utf-8")
    result = mod.build(src, out)
    assert result["count"] == 0
    assert mod.ENTRY.size == 56
    assert len(out.read_bytes()) == 16 + 128 * 56 + 4


def test_catalog_sorts_ids_and_accepts_existing_metrics(tmp_path: Path):
    src = tmp_path / "challenges.json"
    out = tmp_path / "CampaignChallenges.dat"
    src.write_text(json.dumps({
        "format": "rextreme-campaign-challenges",
        "version": 1,
        "challenges": [
            {
                "id": 20,
                "scope": "weekly",
                "metric": "placement",
                "mode": "count_matches",
                "goal": 3,
                "qualifier": {"compare": "le", "threshold": 1},
                "reward": {"credits": 100},
            },
            {
                "id": 10,
                "scope": "daily",
                "metric": "drift_meters",
                "mode": "sum_metric",
                "goal": 1000,
                "reward": {},
            },
        ],
    }), encoding="utf-8")
    result = mod.build(src, out)
    assert result["ids"] == [10, 20]


def test_unknown_metric_is_rejected(tmp_path: Path):
    src = tmp_path / "challenges.json"
    out = tmp_path / "out.dat"
    src.write_text(json.dumps({
        "format": "rextreme-campaign-challenges",
        "version": 1,
        "challenges": [{
            "id": 1,
            "scope": "daily",
            "metric": "invented_effect",
            "mode": "sum_metric",
            "goal": 1,
        }],
    }), encoding="utf-8")
    try:
        mod.build(src, out)
    except mod.ChallengeError as exc:
        assert "invalid metric" in str(exc)
    else:
        raise AssertionError("invented challenge metric was accepted")
