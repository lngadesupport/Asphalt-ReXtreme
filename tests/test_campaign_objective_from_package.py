import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "build_campaign_objective_catalog_from_package.py"

spec = importlib.util.spec_from_file_location("objective_from_package", MODPATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)


class ObjectiveFromPackageTests(unittest.TestCase):
    def test_flat_star_fields(self):
        career = {
            "events": [{
                "eventid": 101,
                "first_star_type": "position",
                "first_star_value": 1,
                "second_star_type": "barrel_rolls",
                "second_star_value": 2,
                "third_star_type": "drift_meters",
                "third_star_value": 300,
            }]
        }
        rows, unresolved = m.convert(career)
        self.assertEqual(unresolved, [])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["metric"], "placement")
        self.assertEqual(rows[0]["compare"], "<=")
        self.assertEqual(rows[1]["metric"], "barrel_rolls")
        self.assertEqual(rows[1]["compare"], ">=")

    def test_nested_objective_list(self):
        career = {
            "events": [{
                "eventid": 202,
                "objectives": [
                    {"type": "finish_time_ms", "value": 90000},
                    {"metric": "wrecked_cars", "threshold": 4},
                    {"goal_type": "nitro_chain", "target": 3},
                ],
            }]
        }
        rows, unresolved = m.convert(career)
        self.assertEqual(unresolved, [])
        self.assertEqual([r["objective_index"] for r in rows], [1, 2, 3])
        self.assertEqual(rows[0]["compare"], "<=")
        self.assertEqual(rows[2]["compare"], ">=")

    def test_unknown_type_fails_closed(self):
        career = {
            "events": [{
                "eventid": 303,
                "first_star_type": "teleport_through_rings",
                "first_star_value": 5,
            }]
        }
        rows, unresolved = m.convert(career)
        self.assertEqual(rows, [])
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0]["reason"], "unknown objective type")

    def test_missing_objective_structure_is_reported(self):
        career = {"events": [{"eventid": 404, "money_for_playing": 1000}]}
        rows, unresolved = m.convert(career)
        self.assertEqual(rows, [])
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0]["reason"], "no recognized objective structure")


if __name__ == "__main__":
    unittest.main()
