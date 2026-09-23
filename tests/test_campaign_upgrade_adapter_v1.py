import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODPATH = ROOT / "tools" / "campaign_upgrade_adapter_v1.py"

spec = importlib.util.spec_from_file_location("campaign_upgrade_adapter_v1", MODPATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)


def test_patch_is_exact_size_replacement():
    assert len(m.PATCHED) == len(m.ORIGINAL) == 142


def test_gateway_selector_is_embedded():
    assert m.UPGRADE_LEGACY_MAGIC.to_bytes(4, "little") in m.PATCHED


def test_original_signature_matches_verified_manager():
    assert m.ORIGINAL.startswith(bytes.fromhex("55 8B EC 6A FF 68 F9 B5 3D 01"))


def test_stub_preserves_original_stack_cleanup():
    assert m.PATCHED.endswith(bytes.fromhex("C2 14 00"))


def test_stub_returns_null_remote_shared_result():
    assert bytes.fromhex("C7 07 00 00 00 00") in m.PATCHED
    assert bytes.fromhex("C7 47 04 00 00 00 00") in m.PATCHED
