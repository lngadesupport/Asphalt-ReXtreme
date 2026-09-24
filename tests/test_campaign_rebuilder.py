import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from campaign_rebuilder import (
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

    def test_status_never_claims_portable_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status_path = write_status(
                root,
                [],
                ["AppxManifest.xml"],
                [],
                {"catalog": "CampaignPresentationOptions.dat", "report": "CampaignPresentationOptions.report.json", "count": 0, "safe_empty_catalog": True},
            )
            data = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(data["edition"], "Campaign")
            self.assertFalse(data["portable_startup_ready"])


if __name__ == "__main__":
    unittest.main()
