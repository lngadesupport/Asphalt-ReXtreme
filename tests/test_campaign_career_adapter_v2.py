import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "campaign_career_adapter_v2.py"

spec = importlib.util.spec_from_file_location("campaign_career_adapter_v2", MODPATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)


def test_verified_service_replacements_are_bounded():
    assert len(m.PRE_SITE_PATCH) == 5
    assert len(m.PRE_STUB) == len(m.PRE_STUB_ORIG) == 85
    assert len(m.POST_FACTORY_STUB) == len(m.POST_FACTORY_ORIG) == 18
    assert len(m.POST_NOTIFY_STUB) == len(m.POST_NOTIFY_ORIG) == 78


def test_pre_stub_uses_verified_career_fields_and_selector():
    blob = m.PRE_STUB
    assert bytes.fromhex("8B 86 F8 00 00 00") in blob
    assert bytes.fromhex("8B 86 FC 00 00 00") in blob
    assert m.CAREER_BEGIN_MAGIC.to_bytes(4, "little") in blob


def test_remote_race_token_is_zeroed():
    assert bytes.fromhex("C7 86 E0 00 00 00 00 00 00 00") in m.PRE_STUB
    assert bytes.fromhex("C7 86 E4 00 00 00 00 00 00 00") in m.PRE_STUB


def test_post_factory_returns_null_shared_pair():
    assert m.POST_FACTORY_STUB == bytes.fromhex(
        "8B 44 24 04 "
        "C7 00 00 00 00 00 "
        "C7 40 04 00 00 00 00 "
        "C3"
    )


def test_finish_metric_hook_remains_guarded():
    assert len(m.FINISH_STUB) == m.FINISH_CAVE_LEN == 43
    assert m.RACE_FINISH_MAGIC.to_bytes(4, "little") in m.FINISH_STUB


def test_v1_broad_begin_is_recognized_for_retirement():
    assert len(m.V1_BEGIN_STUB) == m.V1_BEGIN_CAVE_LEN == 43
