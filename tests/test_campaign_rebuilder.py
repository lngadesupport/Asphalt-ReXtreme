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
                {"catalog": "CampaignReplayBindings.dat", "report": "CampaignReplayBindings.report.json", "count": 0, "recording_ready": False, "safe_empty_catalog": True},
                {"catalog": "CampaignOriginalUiBindings.dat", "report": "CampaignOriginalUiBindings.report.json", "count": 0, "safe_empty_catalog": True, "original_ui_only": True, "custom_ui_assets_allowed": False, "fallback_if_unmapped": "feature-hidden"},
                {"catalog": "CampaignRaceHudBindings.dat", "report": "CampaignRaceHudBindings.report.json", "count": 0, "safe_empty_catalog": True, "original_elements_only": True, "create_new_hud_widgets": False},
                {"catalog": "CampaignChallenges.dat", "report": "CampaignChallenges.report.json", "count": 0, "state": "UserData/CampaignEdition/ChallengeState.dat", "portable": True},
                {"catalog": "CampaignAchievements.dat", "report": "CampaignAchievements.report.json", "count": 0, "state": "UserData/CampaignEdition/AchievementState.dat", "metrics_source": "CampaignStatistics-v1", "rewards": "none", "portable": True},
                {"catalog": "CampaignSpecialEvents.dat", "report": "CampaignSpecialEvents.report.json", "count": 0, "validated_against_event_catalog": False, "uses_existing_campaign_events_only": True, "online_backend_required": False, "portable": True},
                ["UserData/CampaignEdition/", "UserData/Replays/", "UserData/Screenshots/"],
            )
            data = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(data["edition"], "Campaign")
            self.assertFalse(data["portable_startup_ready"])
            self.assertTrue(data["presentation_values_require_verified_binding"])
            self.assertEqual(data["presentation_binding_catalog"]["count"], 0)
            self.assertEqual(data["photo_binding_catalog"]["count"], 0)
            self.assertFalse(data["photo_free_camera_ready"])
            self.assertEqual(data["replay_binding_catalog"]["count"], 0)
            self.assertFalse(data["replay_recording_ready"])
            self.assertTrue(data["original_ui_only"])
            self.assertFalse(data["custom_in_game_ui_assets_allowed"])
            self.assertEqual(data["unmapped_ui_feature_behavior"], "hidden")
            self.assertEqual(data["original_ui_binding_catalog"]["count"], 0)
            self.assertEqual(data["race_hud_binding_catalog"]["count"], 0)
            self.assertTrue(data["race_hud_original_elements_only"])
            self.assertFalse(data["race_hud_new_widgets_allowed"])
            self.assertEqual(data["challenge_catalog"]["count"], 0)
            self.assertTrue(data["challenge_state_portable"])
            self.assertEqual(data["challenge_metrics_source"], "CampaignRaceMetrics-v1")
            self.assertEqual(data["achievement_catalog"]["count"], 0)
            self.assertTrue(data["achievement_state_portable"])
            self.assertEqual(data["achievement_metrics_source"], "CampaignStatistics-v1")
            self.assertEqual(data["achievement_rewards"], "none")
            self.assertTrue(data["achievement_ui_requires_original_templates"])
            self.assertEqual(data["last_race_result_state"], "UserData/CampaignEdition/LastRaceResult.dat")
            self.assertEqual(data["last_race_result_source"], "Committed CampaignRaceMetrics-v1")
            self.assertTrue(data["last_race_result_portable"])
            self.assertTrue(data["results_ui_requires_original_templates"])
            self.assertEqual(data["special_event_catalog"]["count"], 0)
            self.assertTrue(data["special_events_reuse_campaign_events"])
            self.assertFalse(data["special_events_online_backend_required"])
            self.assertTrue(data["special_events_ui_requires_original_templates"])


if __name__ == "__main__":
    unittest.main()
