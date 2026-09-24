import importlib.util
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools"/"campaign_frontend_garage_v4.py"
spec=importlib.util.spec_from_file_location("garage_v4",P)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

def test_gbbw_callback_preserves_original_stack_cleanup():
    assert m.GBBW_BUILD_STACK_CLEANUP == 8
    assert m.GBBW_BUILD_PATCH[-3:] == b"\xC2\x08\x00"

def test_buildcar_fallback_has_plain_ret():
    assert m.BUILD_PATCH[-1:] == b"\xC3"

def test_selectors_are_distinct():
    assert m.GBBW_BUILD_MAGIC != m.BUILD_MAGIC

def test_pic_gateway_targets_existing_igp_import():
    for va,patch in [
        (m.GBBW_BUILD_CALLBACK_VA,m.GBBW_BUILD_PATCH),
        (m.BUILD_VA,m.BUILD_PATCH),
    ]:
        delta=struct.unpack_from("<I",patch,12)[0]
        pop_next=va+11
        assert (pop_next+delta)&0xffffffff==m.IGP_HTTPPOST_PREF_VA
