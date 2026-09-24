import json
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import build_campaign_production_data as p


def type0(payload: bytes) -> bytes:
    return b"\x00\x00" + payload


def make_fixture(path: Path):
    shop = b"""<AsphaltShopConfiguration>
<Car carId="1"><UpgradePrices>
<Price Id="CAR_PRICE" Price="1000" Currency="credits"/>
<Price Id="UPGRADE_LEVEL_1" Price="100" Currency="credits"/>
<Price Id="UPGRADE_LEVEL_2" Price="200" Currency="credits"/>
</UpgradePrices><ProKitPrices>
<Price Id="PROKIT_LEVEL_1" Price="50" Currency="hardcurrency"/>
</ProKitPrices></Car>
<Car carId="2"><UpgradePrices>
<Price Id="CAR_PRICE" Price="50" Currency="hardcurrency"/>
</UpgradePrices></Car>
</AsphaltShopConfiguration>"""

    serverdb = b"""<root>
<x k_2206374417="CarOne" k_4250631189="1" k_1571869371="D" k_1914113855="100"/>
<x k_2206374417="CarTwo" k_4250631189="2" k_1571869371="C" k_1914113855="200"/>
</root>"""

    career = {
        "seasons": [{"seasonid": 1, "serieid": 1, "index": 1, "carclass": "D"}],
        "events": [
            {
                "eventid": 100, "season": 1, "unlockeventid": 0,
                "money_for_playing": 1000, "position_1": 500,
                "position_2": 250, "position_3": 100,
                "carracerfilter": ""
            },
            {
                "eventid": 101, "season": 1, "unlockeventid": 100,
                "money_for_playing": 2000, "position_1": 1000,
                "position_2": 500, "position_3": 250,
                "carracerfilter": "CarFilter_Car_Buggy_Rage_Comet"
            }
        ]
    }

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("xml/asphaltshop.xtea", type0(shop))
        z.writestr("xml/asphaltserverdb.xtea", type0(serverdb))
        z.writestr("xml/career_data.xtea", type0(json.dumps(career).encode()))


def test_real_data_pipeline_helpers(tmp_path):
    xmlbin = tmp_path / "xml.bin"
    make_fixture(xmlbin)

    src = p.extract_sources(xmlbin)
    shop = p.parse_shop(src["shop"])
    server = p.parse_serverdb(src["serverdb"])
    career = p.parse_career(src["career"])
    seasons, events = p.main_career(career)

    vehicles, audit = p.build_vehicle_rows(shop, server, events, 0.20)
    by_id = {x["car_id"]: x for x in vehicles}

    assert len(seasons) == 1
    assert len(events) == 2
    assert by_id[1]["acquisition_type"] == "credits"
    assert by_id[1]["cost"] == 200
    assert by_id[2]["acquisition_type"] == "premium"
    assert by_id[2]["cost"] == 10
    assert by_id[2]["unlock_node_id"] == 100

    event_rows, _ = p.build_event_rows(events, 2500, 5)
    assert event_rows[0]["participation_credits"] == 1000
    assert event_rows[1]["premium_reward"] == 1

    upgrades, _ = p.build_upgrade_rows(shop, vehicles, 0.20)
    # Two standard levels x four shared performance slots + one prokit x four.
    assert len(upgrades) == 12

    first_upgrade = sorted(
        [x for x in upgrades if x["kind"] == "upgrade"],
        key=lambda x: (x["part_slot"], x["target_level"])
    )[0]
    assert first_upgrade["cost"] == 20

    first_pro = next(x for x in upgrades if x["kind"] == "prokit")
    assert first_pro["cost_type"] == "premium"
    assert first_pro["cost"] == 10


def test_binary_builders_accept_pipeline_rows(tmp_path):
    xmlbin = tmp_path / "xml.bin"
    make_fixture(xmlbin)
    src = p.extract_sources(xmlbin)
    shop = p.parse_shop(src["shop"])
    server = p.parse_serverdb(src["serverdb"])
    _, events = p.main_career(p.parse_career(src["career"]))

    vehicles, _ = p.build_vehicle_rows(shop, server, events, 0.20)
    event_rows, _ = p.build_event_rows(events, 2500, 5)
    upgrades, _ = p.build_upgrade_rows(shop, vehicles, 0.20)

    vb = p.vehicle_binary.build(p.vehicle_binary.normalize(vehicles))
    eb = p.event_binary.build(p.event_binary.normalize(event_rows))
    ub = p.upgrade_binary.build(p.upgrade_binary.normalize(upgrades))

    assert len(vb) == 16 + p.vehicle_binary.MAX * p.vehicle_binary.ENTRY.size + 4
    assert len(eb) == 16 + p.event_binary.MAX * p.event_binary.ENTRY.size + 4
    assert len(ub) == 16 + p.upgrade_binary.MAX * p.upgrade_binary.ENTRY.size + 4
