import importlib.util
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

spec_aux = importlib.util.spec_from_file_location(
    "build_campaign_auxiliary_data",
    TOOLS / "build_campaign_auxiliary_data.py",
)
aux = importlib.util.module_from_spec(spec_aux)
assert spec_aux.loader is not None
spec_aux.loader.exec_module(aux)

spec_ui = importlib.util.spec_from_file_location(
    "build_campaign_upgrade_ui_map",
    TOOLS / "build_campaign_upgrade_ui_map.py",
)
ui = importlib.util.module_from_spec(spec_ui)
assert spec_ui.loader is not None
spec_ui.loader.exec_module(ui)


def test_empty_upgrade_map_is_materialized_fail_closed(tmp_path):
    output = tmp_path / "CampaignUpgradeUiMap.dat"
    report = tmp_path / "CampaignUpgradeUiMap.report.json"

    ready, payload = aux.build_ui_map([], output, report)

    assert ready is False
    assert payload["mapped_count"] == 0
    assert payload["conflict_count"] == 0
    assert payload["fallback"] == "empty-fail-closed"
    assert output.is_file()

    data = output.read_bytes()
    magic, version, count, reserved = struct.unpack_from("<4I", data, 0)
    assert magic == ui.MAGIC
    assert version == ui.VERSION
    assert count == 0
    assert reserved == 0
    assert int.from_bytes(data[-4:], "little") == ui.fnv1a(data[:-4])
