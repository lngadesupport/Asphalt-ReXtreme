import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "build_campaign_upgrade_ui_map.py"

spec = importlib.util.spec_from_file_location("campaign_upgrade_ui_map", MODPATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)


class UpgradeUiMapTests(unittest.TestCase):
    def test_layout_and_sort(self):
        entries = m.normalize([
            {"ui_action_id": 20, "kind": "prokit", "part_slot": 3},
            {"ui_action_id": 10, "kind": "upgrade", "part_slot": 1},
        ])
        self.assertEqual(entries[0][:3], (10, 1, 1))
        self.assertEqual(entries[1][:3], (20, 2, 3))

        data = m.build(entries)
        expected = m.HEADER.size + m.MAX * m.ENTRY.size + 4
        self.assertEqual(len(data), expected)
        stored = int.from_bytes(data[-4:], "little")
        self.assertEqual(stored, m.fnv1a(data[:-4]))

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            m.normalize([
                {"ui_action_id": 5, "kind": "upgrade", "part_slot": 0},
                {"ui_action_id": 5, "kind": "prokit", "part_slot": 1},
            ])


if __name__ == "__main__":
    unittest.main()
