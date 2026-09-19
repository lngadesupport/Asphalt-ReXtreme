# Economy audit — verified 1.7.3.8 data

The decrypted career/shop data now allows the Premium economy to be audited mathematically instead of guessed.

## Main career

- 20 main seasons.
- 300 main career events (15 per season).
- One first-place pass over all 300 events yields **317,790 credits** from the repeatable payout candidate (`money_for_playing + position_1`).
- One-time star rewards total **1,799,250 credits**.
- Main-season completion rewards total **925,000 credits** plus **550 hard currency**.
- Ideal gross credit total for one first-place/three-star clear is about **3,042,040 credits** before spending.

The gross figure is an upper bound; it does not subtract car or upgrade purchases.

## Vehicle shop

The current catalog has 61 active cars:
- 32 have a normal credit price;
- 29 are hardcurrency-only in the original shop data.

For Premium mode, credit-priced cars start at:

`premium_price = original_credit_price × 0.80`

The hardcurrency alternative purchase path should be disabled once a normal offline path exists.

## Mandatory exact-car gates

The main career contains 33 first occurrences of exact-car requirements. **12 are hardcurrency-only in the original shop data**, including the early Rage Comet gate in event 113.

This proves that a flat 20% reduction by itself cannot produce a complete paid-game economy. Mandatory hardcurrency-only cars need one of:
- a progression-aware credit price; or
- a career reward/direct unlock before their first mandatory event.

The audit deliberately does not assign arbitrary conversions yet. `tools/economy_audit.py` reports each gate together with the maximum gross credits accumulated before it so the final balance can be simulated.

## Repeat rewards

Star bonuses are kept separate from normal race payouts. ReXtreme will preserve full normal race payout on every replay and remove any service-side/diminishing-return logic if later runtime testing reveals one.
