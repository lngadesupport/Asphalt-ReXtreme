import importlib.util
import struct
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name,rel):
    p=ROOT/rel
    spec=importlib.util.spec_from_file_location(name,p)
    m=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(m)
    return m

patch=load("rex_patch",Path("tools/rex_patch_frontend.py"))
content=load("rex_content",Path("tools/rex_build_content.py"))

class RexCampaignTests(unittest.TestCase):
    def test_new_frontend_bridge_has_exact_cave_capacity(self):
        self.assertEqual(patch.CAVE_LEN,47)
        self.assertLessEqual(
            len(patch.BOOT_STUB)+len(patch.HOME_STUB),
            patch.CAVE_LEN
        )

    def test_build_render_is_direct_active_presentation(self):
        self.assertEqual(patch.BUILD_RENDER_OFF,0x00574FA7)
        self.assertEqual(patch.BUILD_RENDER_BEFORE,b"\xFF\x75\xD8")
        self.assertEqual(patch.BUILD_RENDER_AFTER,b"\x6A\x01\x90")

    def test_new_selectors_are_separate_namespace(self):
        self.assertEqual(patch.SEL_BOOT,0xDEC0A001)
        self.assertEqual(patch.SEL_HOME,0xDEC0A002)
        self.assertEqual(patch.SEL_BUILD,0xDEC0A003)

    def test_new_content_format_is_not_previous_runtime_format(self):
        rows=[(100,content.REX_FREE,0,1),(200,content.REX_CREDITS,25000,2)]
        data=content.build(rows)
        self.assertEqual(len(data),content.NEW_SIZE)
        magic,version,count,reserved=content.NEW_HEADER.unpack_from(data,0)
        self.assertEqual(magic,content.NEW_MAGIC)
        self.assertEqual(version,content.NEW_VERSION)
        self.assertEqual(count,2)
        self.assertEqual(
            struct.unpack_from("<I",data,len(data)-4)[0],
            content.fnv1a(data[:-4])
        )

if __name__=="__main__":
    unittest.main()
