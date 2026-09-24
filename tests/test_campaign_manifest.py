import importlib.util
import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "patches" / "1.7.3.8-x86.json"
LAB_TOOL = ROOT / "tools" / "pe_appcontainer_lab.py"


def load_lab_module():
    spec = importlib.util.spec_from_file_location("pe_appcontainer_lab", LAB_TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CampaignManifestTests(unittest.TestCase):
    def test_ams_manifest_is_exactly_known_campaign_state(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        ams = next(item for item in data["files"] if item["path"] == "AMS.exe")

        self.assertEqual(
            ams["sha256"],
            "3d48800d37cb799e424abe5e33e07bab3235d11dbfbe2fbf50214cecab3e75c8",
        )
        self.assertEqual(
            ams["patched_sha256"],
            "56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3",
        )
        self.assertEqual(len(ams["patches"]), 11)

        names = {patch["name"] for patch in ams["patches"]}
        self.assertIn(
            "Vungle manager: configure stub without SDK activation",
            names,
        )
        self.assertIn(
            "Vungle platform: force availability false",
            names,
        )
        self.assertIn(
            "Windows CRM store purchase: fail locally without launching Store",
            names,
        )

    def test_ams_patches_are_size_preserving_and_non_overlapping(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        ams = next(item for item in data["files"] if item["path"] == "AMS.exe")

        occupied = []
        for patch in ams["patches"]:
            before = bytes.fromhex(patch["before"])
            after = bytes.fromhex(patch["after"])
            self.assertEqual(
                len(before),
                len(after),
                msg=f"{patch['name']} is not size preserving",
            )
            self.assertGreater(len(before), 0)

            start = int(patch["offset"])
            end = start + len(before)
            for old_start, old_end, old_name in occupied:
                self.assertFalse(
                    start < old_end and end > old_start,
                    msg=f"{patch['name']} overlaps {old_name}",
                )
            occupied.append((start, end, patch["name"]))


class NoAppContainerLabTests(unittest.TestCase):
    def make_pe32(self, dll_characteristics=0x9140, checksum=0x12345678):
        data = bytearray(0x200)
        data[:2] = b"MZ"
        struct.pack_into("<I", data, 0x3C, 0x80)
        data[0x80:0x84] = b"PE\0\0"
        coff = 0x84
        struct.pack_into("<H", data, coff, 0x14C)
        struct.pack_into("<H", data, coff + 16, 0xE0)
        optional = coff + 20
        struct.pack_into("<H", data, optional, 0x10B)
        struct.pack_into("<I", data, optional + 64, checksum)
        struct.pack_into("<H", data, optional + 70, dll_characteristics)
        return bytes(data)

    def test_lab_tool_clears_only_appcontainer_and_checksum(self):
        lab = load_lab_module()
        source = self.make_pe32()
        patched, meta = lab.make_no_appcontainer(source)

        checksum_off = meta["checksum_offset"]
        dll_off = meta["dll_characteristics_offset"]

        self.assertEqual(struct.unpack_from("<I", patched, checksum_off)[0], 0)
        self.assertEqual(struct.unpack_from("<H", patched, dll_off)[0], 0x8140)
        self.assertEqual(meta["old_dll_characteristics"], 0x9140)
        self.assertEqual(meta["new_dll_characteristics"], 0x8140)

        expected = bytearray(source)
        struct.pack_into("<I", expected, checksum_off, 0)
        struct.pack_into("<H", expected, dll_off, 0x8140)
        self.assertEqual(patched, bytes(expected))

    def test_lab_tool_refuses_pe_without_appcontainer(self):
        lab = load_lab_module()
        source = self.make_pe32(dll_characteristics=0x8140)
        with self.assertRaises(lab.PEError):
            lab.make_no_appcontainer(source)


if __name__ == "__main__":
    unittest.main()
