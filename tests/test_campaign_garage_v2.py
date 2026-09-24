import importlib.util
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "campaign_garage_v2.py"

spec = importlib.util.spec_from_file_location("campaign_garage_v2", MODPATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)


def test_gateway_matches_known_v1_bytes():
    gateway, owned_va = m.build_gateway()

    expected = bytes.fromhex(
        "68 DE C0 DE C0 "
        "E8 00 00 00 00 "
        "58 "
        "05 69 00 CC 00 "
        "FF 10 "
        "C3 "
        "8B 44 24 04 "
        "8B 08 "
        "68 11 0A DE C0 "
        "E8 00 00 00 00 "
        "58 "
        "05 50 00 CC 00 "
        "FF 10 "
        "C2 04 00 "
        "CC"
    )

    assert gateway == expected
    assert owned_va == 0x00869FD4


def test_rel32_known_routes():
    build = b"\xE9" + m.rel32(m.BUILD_VA, 5, m.CAVE_VA)
    own = b"\xE9" + m.rel32(m.OWN_VA, 5, 0x00869FD4)

    assert build == bytes.fromhex("E9 5C 26 DE FF")
    assert own == bytes.fromhex("E9 EF 6E A1 FF")


def test_gateway_derives_preferred_iat_without_absolute_patch():
    gateway, _ = m.build_gateway()

    # First gateway call/pop returns preferred VA CAVE_VA+10.
    delta1 = struct.unpack_from("<I", gateway, 12)[0]
    assert (m.CAVE_VA + 10 + delta1) & 0xFFFFFFFF == m.IGP_HTTPPOST_PREF_VA

    # Ownership gateway call/pop returns 0x00869FE4.
    delta2 = struct.unpack_from("<I", gateway, 36)[0]
    assert (0x00869FE4 + delta2) & 0xFFFFFFFF == m.IGP_HTTPPOST_PREF_VA


def test_phase48_signature_is_exactly_reserved_cave_size():
    assert len(m.P48_STUB) == m.P48_CAVE_LEN == 47
