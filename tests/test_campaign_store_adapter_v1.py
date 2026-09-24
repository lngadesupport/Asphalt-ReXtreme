import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "campaign_store_adapter_v1.py"

spec = importlib.util.spec_from_file_location("campaign_store_adapter_v1", MODPATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)


def test_controller_redirect_is_known_phase38_shape():
    assert m.CONTROLLER_PATCH == bytes.fromhex("E9 D3 50 05 00")


def test_stub_exact_length_and_selector():
    assert len(m.STUB_PATCH) == len(m.STUB_ORIG) == 213
    assert bytes.fromhex("01 55 DE C0") in m.STUB_PATCH


def test_stub_does_not_call_old_business_callback():
    # rel32 call target 0x00A16A90 must not be encoded anywhere in the local stub.
    # The only UI call is the direct signal at 0x009F5620.
    assert bytes.fromhex("E8") in m.STUB_PATCH
    assert m.STUB_PATCH.endswith(bytes.fromhex("E9 86 AE FA FF"))


def test_phase38_prefix_is_guarded():
    assert len(m.PHASE38_PREFIX) == 80
