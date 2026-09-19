# Premium economy implementation status

## Phase 1 — validated data patch

A local test build now successfully modifies `asphaltshop.xtea` through the type-0 plaintext path and repacks `xml.bin` without changing the HDR layout.

The conservative Phase-1 transform:
- applies exactly `0.80 × original credit price` to the 32 cars that already have a credit purchase path;
- sets the hardcurrency `CAR_PRICE` alternative to 0 for those cars;
- leaves all 29 hardcurrency-only cars untouched until their conversion is balanced;
- does not yet touch upgrade prices or IAP item definitions.

The resulting `asphaltshop.xtea` fits inside its original 383,898-byte slot and the rebuilt `xml.bin` retains all 60 original data offsets.

## Why the remaining cars need simulation

The 33 exact-car gates in the main career include 12 cars whose original direct purchase is hardcurrency-only.

If those hardcurrency prices are converted using the median credit/hardcurrency relationship of same-class cars, the 33 mandatory cars total roughly **19.5 million credits** after the 20% Premium discount. The original main-career ideal first-clear flow is only about **3.0 million credits** before spending.

Therefore the final paid-game economy must combine:
- credit conversion of hardcurrency-only cars;
- normal reward rebalance;
- preserved full repeat payouts;
- blueprint/card progression where it remains useful;
- upgrade affordability.

`tools/economy_simulator.py` quantifies how many repeat races are needed at each mandatory gate under candidate reward/price settings. No multiplier is considered final until blueprint/card acquisition and upgrade requirements are incorporated.

## Current rule

Do not solve an economy bottleneck by silently giving infinite currency in Premium mode. Sandbox remains the unrestricted mode. Premium must remain a real progression system that can be completed comfortably.
