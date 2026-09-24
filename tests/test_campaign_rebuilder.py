import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from campaign_rebuilder import (
    prepare_portable_user_data,
    quarantine_package_metadata,
    verify_source,
    write_status,
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class CampaignRebuilderTests(unittest.TestCase):
    def test_verify_source_accepts_exact_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b"supported-build"
            (root / "AMS.exe").write_bytes(payload)
            manifest = {
                "files": [{
                    "path": "AMS.exe",
                    "sha256": sha(payload),
                    "patches": [],
                }]
            }
            result = verify_source(root, manifest)
            self.assertEqual(result[0]["state"], "original")

    def test_verify_source_rejects_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AMS.exe").write_bytes(b"unknown")
            manifest = {
                "files": [{
                    "path": "AMS.exe",
                    "sha256": "0" * 64,
                    "patches": [],
                }]
            }
            with self.assertRaises(Exception):
                verify_source(root, manifest)

    def test_package_metadata_is_quarantined_not_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AppxManifest.xml").write_text("<Package/>", encoding="utf-8")
            (root / "AppxMetadata").mkdir()
            (root / "AppxMetadata" / "CodeIntegrity.cat").write_bytes(b"x")

            moved = quarantine_package_metadata(root)

            self.assertIn("AppxManifest.xml", moved)
            self.assertIn("AppxMetadata/", moved)
            self.assertFalse((root / "AppxManifest.xml").exists())
            self.assertTrue((root / "_source_metadata/appx/AppxManifest.xml").exists())
            self.assertTrue((root / "_source_metadata/appx/AppxMetadata/CodeIntegrity.cat").exists())

    def test_prepare_portable_user_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            created = prepare_portable_user_data(root)
            self.assertEqual(
                created,
                [
                    "UserData/CampaignEdition/",
                    "UserData/Replays/",
                    "UserData/Screenshots/",
                ],
            )
            for rel in created:
                self.assertTrue((root / rel.rstrip("/")).is_dir())

    def test_status_never_claims_portable_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status_path = write_status(
                root,
                [],
                ["AppxManifest.xml"],
                [],
                {"catalog": "CampaignPresentationOptions.dat", "report": "CampaignPresentationOptions.report.json", "count": 0, "safe_empty_catalog": True},
                {"catalog": "CampaignPresentationBindings.dat", "report": "CampaignPresentationBindings.report.json", "count": 0, "safe_empty_catalog": True},
                {"catalog": "CampaignPhotoBindings.dat", "report": "CampaignPhotoBindings.report.json", "count": 0, "free_camera_ready": False, "safe_empty_catalog": True},
                ["UserData/CampaignEdition/", "UserData/Replays/", "UserData/Screenshots/"],
            )
            data = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(data["edition"], "Campaign")
            self.assertFalse(data["portable_startup_ready"])
            self.assertTrue(data["presentation_values_require_verified_binding"])
            self.assertEqual(data["presentation_binding_catalog"]["count"], 0)
            self.assertEqual(data["photo_binding_catalog"]["count"], 0)
            self.assertFalse(data["photo_free_camera_ready"])


if __name__ == "__main__":
    unittest.main()
