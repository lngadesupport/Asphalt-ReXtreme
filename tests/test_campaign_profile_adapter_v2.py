import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "tools" / "campaign_profile_adapter_v2.py"
spec = importlib.util.spec_from_file_location("profile_v2", P)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

def image(v1=False):
    size = max(
        m.ONLINE_OFF + len(m.ONLINE_FALSE),
        m.POPUP_OFF + len(m.POPUP_ORIG),
        m.SYNC_SUBMIT_OFF + len(m.SYNC_SUBMIT_ORIG),
        max(off + len(before) for _, off, before, _ in m.PATCHES),
    ) + 16
    d = bytearray(b"\xCC" * size)
    d[m.ONLINE_OFF:m.ONLINE_OFF+len(m.ONLINE_FALSE)] = m.ONLINE_FALSE
    d[m.POPUP_OFF:m.POPUP_OFF+len(m.POPUP_ORIG)] = m.POPUP_ORIG
    d[m.SYNC_SUBMIT_OFF:m.SYNC_SUBMIT_OFF+len(m.SYNC_SUBMIT_ORIG)] = (
        m.SYNC_SUBMIT_V1 if v1 else m.SYNC_SUBMIT_ORIG
    )
    for _, off, before, _ in m.PATCHES:
        d[off:off+len(before)] = before
    return d

def test_v2_preserves_original_global_sync_submit():
    d = image(False)
    m.apply_bytes(d)
    assert d[m.SYNC_SUBMIT_OFF:m.SYNC_SUBMIT_OFF+len(m.SYNC_SUBMIT_ORIG)] == m.SYNC_SUBMIT_ORIG

def test_v2_migrates_v1_by_restoring_global_sync_submit():
    d = image(True)
    m.apply_bytes(d)
    assert d[m.SYNC_SUBMIT_OFF:m.SYNC_SUBMIT_OFF+len(m.SYNC_SUBMIT_ORIG)] == m.SYNC_SUBMIT_ORIG

def test_v2_is_idempotent():
    d = image(False)
    m.apply_bytes(d)
    first = bytes(d)
    m.apply_bytes(d)
    assert bytes(d) == first
