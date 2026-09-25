import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "builder" / "rex_content_v2.py"


def load_builder():
    if not BUILDER_PATH.exists():
        raise AssertionError("ReX V2 content builder is not implemented")
    spec = importlib.util.spec_from_file_location(
        "rex_content_v2",
        BUILDER_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RexContentV2BuilderTests(unittest.TestCase):
    def manifest(self):
        return {
            "schema": 2,
            "vehicles": [
                {
                    "vehicle_id": 501,
                    "unlocked_by_default": True,
                    "recipe": {
                        "blueprint_id": 9501,
                        "cost": 7,
                    },
                },
                {
                    "vehicle_id": 502,
                    "unlocked_by_default": False,
                    "recipe": None,
                },
            ],
            "initial_state": {
                "blueprints": [
                    {
                        "blueprint_id": 9501,
                        "amount": 10,
                    }
                ],
                "owned_vehicles": [502],
            },
        }

    def test_build_bytes_matches_runtime_v2_format(self):
        builder = load_builder()
        payload = builder.build_bytes(self.manifest())

        expected = bytearray(b"REXCTV2\x00")
        expected += struct.pack("<II", 2, 2)
        expected += struct.pack("<IIIII", 501, 1, 1, 9501, 7)
        expected += struct.pack("<IIIII", 502, 0, 0, 0, 0)
        expected += struct.pack("<I", 1)
        expected += struct.pack("<II", 9501, 10)
        expected += struct.pack("<I", 1)
        expected += struct.pack("<I", 502)

        self.assertEqual(payload, bytes(expected))

    def test_duplicate_vehicle_id_is_rejected(self):
        builder = load_builder()
        document = self.manifest()
        document["vehicles"].append(
            {
                "vehicle_id": 501,
                "unlocked_by_default": True,
                "recipe": None,
            }
        )

        with self.assertRaisesRegex(ValueError, "duplicate vehicle_id"):
            builder.build_bytes(document)

    def test_build_file_is_deterministic(self):
        builder = load_builder()
        document = self.manifest()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "manifest.json"
            first = root / "first.dat"
            second = root / "second.dat"
            source.write_text(
                json.dumps(document),
                encoding="utf-8",
            )

            builder.build_file(source, first)
            builder.build_file(source, second)

            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
