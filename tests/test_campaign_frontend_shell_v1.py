import importlib.util, struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools"/"campaign_frontend_shell_v1.py"
spec=importlib.util.spec_from_file_location("shell",P)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

def test_build_path_has_no_original_object_dependency():
    p=m.gateway_return(m.BUILD_CALLBACK_VA,m.RT_BUILD_SELECTED,m.BUILD_CALLBACK_STACK)
    assert p[:5]==b"\x68"+struct.pack("<I",m.RT_BUILD_SELECTED)
    assert p[-3:]==b"\xC2\x08\x00"

def test_clean_runtime_selectors_only():
    assert m.RT_BOOT==0xC0DE9005
    assert m.RT_LOBBY==0xC0DE9006
    assert m.RT_BUILD_SELECTED==0xC0DE9003
