import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "campaign_profile_adapter_v1.py"

spec = importlib.util.spec_from_file_location("campaign_profile_adapter_v1", MODPATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)


def make_image():
    size = max(
        m.ONLINE_OFF + len(m.ONLINE_FALSE),
        m.POPUP_OFF + len(m.POPUP_ORIG),
        m.SYNC_SUBMIT_OFF + len(m.SYNC_SUBMIT_ORIG),
        max(off + len(before) for _, off, before, _ in m.PATCHES),
    ) + 16
    d = bytearray(b"\xCC" * size)
    d[m.ONLINE_OFF:m.ONLINE_OFF + len(m.ONLINE_FALSE)] = m.ONLINE_FALSE
    d[m.POPUP_OFF:m.POPUP_OFF + len(m.POPUP_ORIG)] = m.POPUP_ORIG
    d[m.SYNC_SUBMIT_OFF:m.SYNC_SUBMIT_OFF + len(m.SYNC_SUBMIT_ORIG)] = m.SYNC_SUBMIT_ORIG
    for _, off, before, _ in m.PATCHES:
        d[off:off + len(before)] = before
    return d


def test_profile_adapter_patches_all_known_sync_sites():
    d = make_image()
    changes = m.apply_bytes(d)

    assert len(changes) == len(m.PATCHES) + 2
    assert d[m.ONLINE_OFF:m.ONLINE_OFF + len(m.ONLINE_FALSE)] == m.ONLINE_FALSE
    assert d[m.POPUP_OFF:m.POPUP_OFF + len(m.POPUP_SAFE)] == m.POPUP_SAFE
    assert d[m.SYNC_SUBMIT_OFF:m.SYNC_SUBMIT_OFF + len(m.SYNC_SUBMIT_LOCAL)] == m.SYNC_SUBMIT_LOCAL

    for _, off, _, after in m.PATCHES:
        assert d[off:off + len(after)] == after


def test_profile_adapter_is_idempotent():
    d = make_image()
    m.apply_bytes(d)
    first = bytes(d)
    m.apply_bytes(d)
    assert bytes(d) == first
