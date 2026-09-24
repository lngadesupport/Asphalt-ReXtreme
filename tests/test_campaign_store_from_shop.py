import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_campaign_store_from_shop as s


def test_non_car_local_offer():
    xml = b"""<AsphaltShopConfiguration>
      <Boosters>
        <Booster Id="nitro_booster" Quantity="3">
          <Price Id="BOOST_NITRO" Price="10000" Currency="credits"/>
        </Booster>
      </Boosters>
    </AsphaltShopConfiguration>"""
    rows, audit, collisions = s.build_rows(xml, 0.20)
    assert not collisions
    assert rows
    assert rows[0]["price"] == 2000
    assert rows[0]["currency"] == "credits"
    assert rows[0]["quantity"] == 3
    assert {r["offer_key"] for r in rows} >= {"nitro_booster", "BOOST_NITRO"}


def test_car_is_excluded():
    xml = b"""<AsphaltShopConfiguration>
      <Car carId="1"><UpgradePrices>
        <Price Id="CAR_PRICE" Price="100000" Currency="credits"/>
      </UpgradePrices></Car>
    </AsphaltShopConfiguration>"""
    rows, _, collisions = s.build_rows(xml, 0.20)
    assert rows == []
    assert not collisions


def test_prefers_credits_over_hardcurrency():
    xml = b"""<AsphaltShopConfiguration>
      <Box Id="parts_box">
        <Price Id="BOX_HARD" Price="100" Currency="hardcurrency"/>
        <Price Id="BOX_CREDITS" Price="50000" Currency="credits"/>
      </Box>
    </AsphaltShopConfiguration>"""
    rows, _, _ = s.build_rows(xml, 0.20)
    assert rows
    assert all(r["currency"] == "credits" for r in rows)
    assert all(r["price"] == 10000 for r in rows)


def test_iap_is_excluded():
    xml = b"""<AsphaltShopConfiguration>
      <IAPBundle Id="real_money_pack">
        <Price Id="MONEY" Price="5" Currency="credits"/>
      </IAPBundle>
    </AsphaltShopConfiguration>"""
    rows, _, _ = s.build_rows(xml, 0.20)
    assert rows == []
