import importlib.util
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools"/"campaign_offline_surface_v5.py"
spec=importlib.util.spec_from_file_location("offline_v5",P)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

def test_filter_is_exactly_47_bytes_and_preserves_original_prologue():
    cave_va=0x00600000
    popup_va=0x00D174B0
    code=m.build_popup_filter(cave_va,popup_va)
    assert len(code)==47
    assert code[34:37]==bytes.fromhex("C2 18 00")
    assert code[37:42]==m.POPUP_ORIG
    rel=struct.unpack_from("<i",code,43)[0]
    assert cave_va+47+rel==popup_va+5

def test_protected_caves_overlap_guard():
    assert m.overlaps_protected(0x004693C1,0x004693C1+m.FILTER_LEN)
    assert m.overlaps_protected(0x00CE8FA5,0x00CE8FA5+m.FILTER_LEN)
    assert not m.overlaps_protected(0x00500000,0x00500000+m.FILTER_LEN)


def test_isolated_legacy_cave_fallback():
    data = bytearray(b"\x90" * 0x00500000)
    data[m.LEGACY_FILTER_CAVE_OFF:m.LEGACY_FILTER_CAVE_OFF+m.FILTER_LEN] = b"\xCC" * m.FILTER_LEN
    sections = [{
        "raw": 0,
        "raw_size": len(data),
        "chars": 0x20000000,
    }]
    off = m.find_exec_cave(bytes(data), sections, allow_legacy_cave=True)
    assert off == m.LEGACY_FILTER_CAVE_OFF
