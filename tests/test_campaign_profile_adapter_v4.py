import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools"/"campaign_profile_adapter_v4.py"
spec=importlib.util.spec_from_file_location("profile_v4",P)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def image():
    rows=m.PROFILE_PATCHES+m.OFFLINE_UI_PATCHES
    size=max([m.ONLINE_OFF+len(m.ONLINE_FALSE)]+[off+len(b) for _,off,b,_ in rows])+16
    d=bytearray(b"\xCC"*size)
    d[m.ONLINE_OFF:m.ONLINE_OFF+len(m.ONLINE_FALSE)]=m.ONLINE_FALSE
    for _,off,before,_ in rows:d[off:off+len(before)]=before
    return d

def test_v4_patches_all_known_offline_ui_routes():
    d=image(); m.apply_bytes(d)
    assert d[m.ONLINE_OFF:m.ONLINE_OFF+len(m.ONLINE_FALSE)]==m.ONLINE_FALSE
    for _,off,_,after in m.PROFILE_PATCHES+m.OFFLINE_UI_PATCHES:
        assert d[off:off+len(after)]==after

def test_v4_is_idempotent():
    d=image(); m.apply_bytes(d); first=bytes(d); m.apply_bytes(d); assert bytes(d)==first
