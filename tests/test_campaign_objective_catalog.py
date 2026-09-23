import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "build_campaign_objective_catalog.py"

spec = importlib.util.spec_from_file_location("build_campaign_objective_catalog", MODPATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)


class CampaignObjectiveCatalogTests(unittest.TestCase):
    def test_binary_layout_sorting_and_checksum(self):
        rows = [
            {
                "event_id": 20,
                "objective_index": 2,
                "metric": "barrel_rolls",
                "compare": ">=",
                "threshold": 2,
                "stars": 1,
            },
            {
                "event_id": 10,
                "objective_index": 1,
                "metric": "placement",
                "compare": "<=",
                "threshold": 1,
                "stars": 1,
            },
        ]

        entries = m.normalize(rows)
        self.assertEqual(entries[0][:6], (10, 1, 1, 1, 1, 1))
        self.assertEqual(entries[1][:6], (20, 2, 10, 2, 2, 1))

        data = m.build(entries)
        expected_size = m.HEADER.size + m.MAX * m.ENTRY.size + m.CHECKSUM.size
        self.assertEqual(len(data), expected_size)

        magic, version, count, reserved = m.HEADER.unpack_from(data, 0)
        self.assertEqual(magic, m.MAGIC)
        self.assertEqual(version, 1)
        self.assertEqual(count, 2)
        self.assertEqual(reserved, 0)

        checksum = m.CHECKSUM.unpack_from(data, len(data) - 4)[0]
        self.assertEqual(checksum, m.fnv1a(data[:-4]))

    def test_duplicate_objective_rejected(self):
        rows = [
            {"event_id": 1, "objective_index": 1, "metric": "placement", "compare": "<=", "threshold": 1},
            {"event_id": 1, "objective_index": 1, "metric": "finish_time_ms", "compare": "<=", "threshold": 1000},
        ]
        with self.assertRaises(ValueError):
            m.normalize(rows)

    def test_unknown_metric_rejected(self):
        with self.assertRaises(ValueError):
            m.normalize([{
                "event_id": 1,
                "objective_index": 1,
                "metric": "server_magic",
                "compare": ">=",
                "threshold": 1,
            }])


if __name__ == "__main__":
    unittest.main()
