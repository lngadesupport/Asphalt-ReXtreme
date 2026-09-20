from tools.make_premium_shop import transform_shop


def test_vehicle_prices_are_80_percent_and_currency_is_preserved():
    source = """<Root>
<Car carId="22">
  <Price Id="CAR_PRICE" Price="33000" Currency="credits" />
</Car>
<Car carId="2">
  <Price Id="CAR_PRICE" Price="340" Currency="hardcurrency" />
</Car>
</Root>"""

    output, report = transform_shop(source, 0.80)

    assert 'Price="26400" Currency="credits"' in output
    assert 'Price="272" Currency="hardcurrency"' in output
    assert report["cars_changed"] == 2
    assert report["credits_changes"] == 1
    assert report["hardcurrency_changes"] == 1
