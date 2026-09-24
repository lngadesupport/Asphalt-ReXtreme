import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_campaign_auxiliary_data as a


def test_verified_part_enum():
    assert a.part_value("topSpeed") == 0
    assert a.part_value("top_speed") == 0
    assert a.part_value("acceleration") == 1
    assert a.part_value("handling") == 2
    assert a.part_value("nitro") == 3


def test_strict_upgrade_candidate():
    row = a.candidate_from_record(
        {"id": "12345", "car_part": "handling", "type": "upgrade_card"},
        "cards.json",
        "$.cards[0]",
    )
    assert not row["unresolved"]
    assert row["ui_action_id"] == 12345
    assert row["kind"] == "upgrade"
    assert row["part_slot"] == 2


def test_ambiguous_id_fails_closed():
    row = a.candidate_from_record(
        {"id": "123", "item_id": "456", "car_part": "nitro", "type": "upgrade"},
        "cards.json",
        "$",
    )
    assert row["unresolved"]


def test_prokit_kind():
    row = a.candidate_from_record(
        {"tool_id": 44, "carPart": "topSpeed", "category": "prokit"},
        "prokits.xml",
        "/tools/tool",
    )
    assert not row["unresolved"]
    assert row["kind"] == "prokit"
    assert row["part_slot"] == 0
