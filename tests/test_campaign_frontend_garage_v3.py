import importlib.util
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools"/"campaign_frontend_garage_v3.py"
spec=importlib.util.spec_from_file_location("garage_v3",P)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

def test_direct_button_callback_and_fallback_have_distinct_selectors():
    assert m.GBBW_BUILD_MAGIC != m.BUILD_MAGIC
    assert len(m.GBBW_BUILD_PATCH)==19
    assert len(m.BUILD_PATCH)==19
    assert m.GBBW_BUILD_PATCH[:5]==b"\x68"+struct.pack("<I",m.GBBW_BUILD_MAGIC)
    assert m.BUILD_PATCH[:5]==b"\x68"+struct.pack("<I",m.BUILD_MAGIC)

def test_both_stubs_are_direct_local_returns():
    assert m.GBBW_BUILD_PATCH[-1:]==b"\xC3"
    assert m.BUILD_PATCH[-1:]==b"\xC3"

def test_pic_gateway_targets_existing_igp_import():
    for va,patch in [
        (m.GBBW_BUILD_CALLBACK_VA,m.GBBW_BUILD_PATCH),
        (m.BUILD_VA,m.BUILD_PATCH),
    ]:
        delta=struct.unpack_from("<I",patch,12)[0]
        pop_next=va+11
        assert (pop_next+delta)&0xffffffff==m.IGP_HTTPPOST_PREF_VA
