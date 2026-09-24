import importlib.util
import struct
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools"/"campaign_frontend_shell_v1.py"
spec=importlib.util.spec_from_file_location("shell",P)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

class CleanFrontendShellTests(unittest.TestCase):
    def test_build_path_has_no_original_object_dependency(self):
        p=m.gateway_return(
            m.BUILD_CALLBACK_VA,
            m.RT_BUILD_SELECTED,
            m.BUILD_CALLBACK_STACK
        )
        self.assertEqual(
            p[:5],
            b"\x68"+struct.pack("<I",m.RT_BUILD_SELECTED)
        )
        self.assertEqual(p[-3:],b"\xC2\x08\x00")

    def test_exact_frontend_cave_size(self):
        self.assertEqual(m.CAVE_LEN,47)
        self.assertLessEqual(len(m.BOOT_STUB)+len(m.LOBBY_STUB),m.CAVE_LEN)

    def test_clean_runtime_selectors_only(self):
        self.assertEqual(m.RT_BOOT,0xC0DE9005)
        self.assertEqual(m.RT_LOBBY,0xC0DE9006)
        self.assertEqual(m.RT_BUILD_SELECTED,0xC0DE9003)

if __name__=="__main__":
    unittest.main()
