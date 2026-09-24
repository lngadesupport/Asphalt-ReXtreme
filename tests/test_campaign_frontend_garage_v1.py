import importlib.util
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools"/"campaign_frontend_garage_v1.py"
spec=importlib.util.spec_from_file_location("garage_v1",P)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

def test_build_stub_is_in_place_and_no_cave_needed():
    assert len(m.BUILD_PATCH)==19
    assert m.BUILD_PATCH[:5]==b"\x68"+struct.pack("<I",m.GARAGE_BUILD_MAGIC)
    assert m.BUILD_PATCH[-1:]==b"\xC3"

def test_ownership_stub_preserves_thiscall_stack_cleanup():
    assert len(m.OWN_PATCH)==21
    assert m.OWN_PATCH[:5]==b"\x68"+struct.pack("<I",m.OWNERSHIP_MAGIC)
    assert m.OWN_PATCH[-3:]==bytes.fromhex("C2 04 00")

def test_pic_iat_targets_existing_import():
    delta=struct.unpack_from("<I",m.BUILD_PATCH,12)[0]
    pop_next=m.BUILD_VA+11
    assert (pop_next+delta)&0xffffffff==m.IGP_HTTPPOST_PREF_VA
