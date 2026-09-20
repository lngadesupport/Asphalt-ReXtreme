# Campaign economy implementation status

## Current implemented tooling rules

The Campaign Edition tooling now uses the agreed default content price rule:

```text
new_price = round(original_price * 0.20)
```

That is an **80% discount**.

Updated tools:
- `tools/rextreme_economy.py`;
- `tools/rebalance_economy.py`;
- `tools/make_premium_shop.py`;
- `tools/economy_simulator.py`.

The simulator also models the repeat-reward rule:
- runs 1-10: 100%;
- after run 10: -0.2 percentage points per additional repeat;
- floor: 98%.

## Existing validated data path

A previous local test build successfully modified `asphaltshop.xtea` through the type-0 plaintext path and repacked `xml.bin` without changing the HDR layout.

That proves the shop-data transformation path exists. The earlier 0.80 multiplier experiment is superseded by the Campaign Edition 0.20 rule.

## Remaining economy work

The final game-data patch still needs:
- all shop content categories audited, not only direct car prices;
- paint/customization prices converted;
- upgrade/part prices converted;
- hardcurrency-only car progression balanced;
- premium currency awarded from races at runtime/data level;
- ad-gated content converted to normal purchases/rewards;
- real-money currency packs/IAP UI disabled or removed;
- per-event repeat counters connected to the 98% floor rule;
- fresh-save full-career simulation and runtime verification.

## Constraint

Campaign mode must remain a real progression system. Unlimited resources belong only to an optional separate Sandbox mode.
