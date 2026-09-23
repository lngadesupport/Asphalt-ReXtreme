import importlib.util
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "build_campaign_vehicle_catalog.py"

spec = importlib.util.spec_from_file_location("catalog_builder", MODPATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)


def test_catalog_binary_layout_and_checksum():
    rows = [
        {
            "car_id": 20,
            "acquisition_type": "credits",
            "item_id": 0,
            "cost": 50000,
            "unlock_node_id": 4,
            "class_id": 2,
            "flags": 0,
        },
        {
            "car_id": 10,
            "acquisition_type": "blueprint",
            "item_id": 5010,
            "cost": 8,
            "unlock_node_id": 0,
            "class_id": 1,
            "flags": 0,
        },
    ]

    entries = m.normalize(rows)
    assert [x[0] for x in entries] == [10, 20]

    data = m.build(entries)
    assert len(data) == 16 + (m.MAX * m.ENTRY.size) + 4

    magic, version, count, reserved = m.HEADER.unpack_from(data, 0)
    assert magic == m.MAGIC
    assert version == m.VERSION
    assert count == 2
    assert reserved == 0

    first = m.ENTRY.unpack_from(data, 16)
    second = m.ENTRY.unpack_from(data, 16 + m.ENTRY.size)

    assert first[:4] == (10, m.TYPE["blueprint"], 5010, 8)
    assert second[:4] == (20, m.TYPE["credits"], 0, 50000)

    stored = struct.unpack_from("<I", data, len(data) - 4)[0]
    assert stored == m.fnv1a(data[:-4])


def test_catalog_rejects_duplicate_and_invalid_item_semantics():
    dup = [
        {"car_id": 1, "acquisition_type": "free", "item_id": 0, "cost": 0},
        {"car_id": 1, "acquisition_type": "credits", "item_id": 0, "cost": 1},
    ]

    try:
        m.normalize(dup)
        assert False, "duplicate car id should fail"
    except ValueError:
        pass

    bad = [
        {"car_id": 2, "acquisition_type": "credits", "item_id": 99, "cost": 10},
    ]
    try:
        m.normalize(bad)
        assert False, "non-blueprint item_id should fail"
    except ValueError:
        pass
