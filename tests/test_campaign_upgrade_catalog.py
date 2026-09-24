import importlib.util
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "build_campaign_upgrade_catalog.py"
spec = importlib.util.spec_from_file_location("campaign_upgrade_catalog", MODPATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)


def test_upgrade_catalog_layout_and_sorting():
    rows = [
        {"car_id": 2, "kind": "prokit", "part_slot": 1, "target_level": 1,
         "cost_type": "inventory", "item_id": 99, "cost": 2},
        {"car_id": 1, "kind": "upgrade", "part_slot": 0, "target_level": 1,
         "cost_type": "credits", "item_id": 0, "cost": 2000},
    ]
    entries = m.normalize(rows)
    assert entries[0][:4] == (1, 1, 0, 1)
    assert entries[1][:4] == (2, 2, 1, 1)

    data = m.build(entries)
    assert len(data) == 16 + m.MAX * m.ENTRY.size + 4
    assert struct.unpack_from("<I", data, len(data)-4)[0] == m.fnv1a(data[:-4])


def test_upgrade_catalog_rejects_bad_inventory_semantics():
    try:
        m.normalize([
            {"car_id": 1, "kind": "upgrade", "part_slot": 0, "target_level": 1,
             "cost_type": "inventory", "item_id": 0, "cost": 1}
        ])
        assert False
    except ValueError:
        pass


def test_production_scale_upgrade_catalog():
    rows = []
    for car_id in range(1, 62):
        for kind in ("upgrade", "prokit"):
            for part_slot in range(4):
                for target_level in range(1, 17):
                    rows.append({
                        "car_id": car_id,
                        "kind": kind,
                        "part_slot": part_slot,
                        "target_level": target_level,
                        "cost_type": "credits",
                        "item_id": 0,
                        "cost": 1000 + target_level,
                    })
    entries = m.normalize(rows)
    assert len(entries) == 7808
    assert len(entries) < m.MAX
    data = m.build(entries)
    assert len(data) == 16 + m.MAX * m.ENTRY.size + 4
