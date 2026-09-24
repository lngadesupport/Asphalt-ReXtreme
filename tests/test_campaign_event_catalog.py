import importlib.util
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "build_campaign_event_catalog.py"

spec = importlib.util.spec_from_file_location("campaign_event_catalog", MODPATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)


def test_event_catalog_binary_layout_and_checksum():
    rows = [
        {
            "event_id": 20,
            "required_node_id": 10,
            "completion_node_id": 20,
            "participation_credits": 1000,
            "position1_credits": 2000,
            "position2_credits": 1000,
            "position3_credits": 500,
            "premium_reward": 3,
            "max_stars": 3,
            "flags": 0,
        },
        {
            "event_id": 10,
            "required_node_id": 0,
            "completion_node_id": 10,
            "participation_credits": 500,
            "position1_credits": 1000,
            "position2_credits": 500,
            "position3_credits": 250,
            "premium_reward": 1,
            "max_stars": 3,
            "flags": 0,
        },
    ]

    entries = m.normalize(rows)
    assert [x[0] for x in entries] == [10, 20]

    data = m.build(entries)
    assert len(data) == 16 + m.MAX * m.ENTRY.size + 4

    magic, version, count, reserved = m.HEADER.unpack_from(data, 0)
    assert magic == m.MAGIC
    assert version == m.VERSION
    assert count == 2
    assert reserved == 0

    first = m.ENTRY.unpack_from(data, 16)
    assert first[:4] == (10, 0, 10, 500)

    stored = struct.unpack_from("<I", data, len(data) - 4)[0]
    assert stored == m.fnv1a(data[:-4])


def test_event_catalog_rejects_duplicates_and_negative_rewards():
    try:
        m.normalize([
            {"event_id": 1},
            {"event_id": 1},
        ])
        assert False
    except ValueError:
        pass

    try:
        m.normalize([
            {"event_id": 2, "participation_credits": -1},
        ])
        assert False
    except ValueError:
        pass
