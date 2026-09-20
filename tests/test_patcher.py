import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from patcher import PatchError, patch_file


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PatcherTests(unittest.TestCase):
    def make_entry(self, original: bytes, patched: bytes):
        return {
            "path": "fixture.bin",
            "sha256": sha(original),
            "patched_sha256": sha(patched),
            "patches": [
                {
                    "name": "fixture patch",
                    "offset": 4,
                    "before": original[4:8].hex(" "),
                    "after": patched[4:8].hex(" "),
                }
            ],
        }

    def test_patch_and_idempotence(self):
        original = b"ABCD1234WXYZ"
        patched = b"ABCD5678WXYZ"
        entry = self.make_entry(original, patched)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.bin"
            path.write_bytes(original)

            state = patch_file(path, entry, dry_run=False)
            self.assertEqual(state, "patched")
            self.assertEqual(path.read_bytes(), patched)
            self.assertEqual(path.with_suffix(".bin.rex.bak").read_bytes(), original)

            state = patch_file(path, entry, dry_run=False)
            self.assertEqual(state, "already-patched")
            self.assertEqual(path.read_bytes(), patched)

    def test_dry_run_does_not_write(self):
        original = b"ABCD1234WXYZ"
        patched = b"ABCD5678WXYZ"
        entry = self.make_entry(original, patched)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.bin"
            path.write_bytes(original)
            state = patch_file(path, entry, dry_run=True)
            self.assertEqual(state, "dry-run")
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(path.with_suffix(".bin.rex.bak").exists())

    def test_unknown_hash_refused(self):
        original = b"ABCD1234WXYZ"
        patched = b"ABCD5678WXYZ"
        entry = self.make_entry(original, patched)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.bin"
            path.write_bytes(b"ABCD9999WXYZ")
            with self.assertRaises(PatchError):
                patch_file(path, entry, dry_run=False)

    def test_wrong_final_hash_refused_before_write(self):
        original = b"ABCD1234WXYZ"
        patched = b"ABCD5678WXYZ"
        entry = self.make_entry(original, patched)
        entry["patched_sha256"] = "0" * 64

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.bin"
            path.write_bytes(original)
            with self.assertRaises(PatchError):
                patch_file(path, entry, dry_run=False)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(path.with_suffix(".bin.rex.bak").exists())


if __name__ == "__main__":
    unittest.main()
