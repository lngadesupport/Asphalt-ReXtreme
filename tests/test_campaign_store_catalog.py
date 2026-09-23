import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "build_campaign_store_catalog.py"

spec = importlib.util.spec_from_file_location("build_campaign_store_catalog", MODPATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)


class CampaignStoreCatalogTests(unittest.TestCase):
    def test_binary_layout_and_sorting(self):
        rows = [
            {"offer_id": 20, "item_id": 200, "quantity": 2, "currency": "premium", "price": 75},
            {"offer_id": 10, "item_id": 100, "quantity": 5, "currency": "credits", "price": 10000},
        ]
        data = m.encode(rows)

        expected_size = m.HEADER.size + m.MAX_OFFERS * m.ENTRY.size + m.CHECKSUM.size
        self.assertEqual(len(data), expected_size)

        magic, version, count, reserved = m.HEADER.unpack_from(data, 0)
        self.assertEqual(magic, m.MAGIC)
        self.assertEqual(version, 1)
        self.assertEqual(count, 2)
        self.assertEqual(reserved, 0)

        first = m.ENTRY.unpack_from(data, m.HEADER.size)
        second = m.ENTRY.unpack_from(data, m.HEADER.size + m.ENTRY.size)
        self.assertEqual(first[:5], (10, 100, 5, 1, 10000))
        self.assertEqual(second[:5], (20, 200, 2, 2, 75))

        stored_checksum = m.CHECKSUM.unpack_from(data, len(data) - 4)[0]
        self.assertEqual(stored_checksum, m.fnv1a(data[:-4]))

    def test_free_offer_requires_zero_price(self):
        with self.assertRaises(ValueError):
            m.encode([{
                "offer_id": 1,
                "item_id": 2,
                "quantity": 1,
                "currency": "free",
                "price": 1,
            }])

    def test_loader_schema(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "store.json"
            p.write_text(json.dumps({"schema": 1, "offers": []}), encoding="utf-8")
            self.assertEqual(m.load(p), [])


if __name__ == "__main__":
    unittest.main()
