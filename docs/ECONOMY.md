# Campaign Edition Economy

The default economy is designed as a traditional paid racing game rather than a free-to-play service.

## Core rules

- No real-money purchases are required for progression.
- No rewarded-ad gates.
- No energy/fuel system that blocks continued play.
- No monetization timers or pay-to-skip waits.
- No Microsoft Store or Gameloft IAP dependency.
- Normal credits and premium currency are both earned through gameplay.
- Every locally present car, upgrade and campaign event must be obtainable offline.
- The shop remains visually/functionally close to the original where possible.

## Shop pricing

Campaign Edition applies an **80% discount** to normal content prices:

```text
campaign_price = round(original_price * 0.20)
```

Applies to:
- cars;
- paint/customization;
- upgrades;
- parts;
- other normal shop content.

Examples:

```text
Original 10,000  -> Campaign 2,000
Original 50,000  -> Campaign 10,000
Original 125,000 -> Campaign 25,000
```

Currency packs sold for real money are not treated as normal shop content and are removed from the progression model.

## Premium currency

Premium currency remains a distinct gameplay resource, but it is no longer tied to real-money purchase.

Race completion grants:
- normal credits;
- premium currency.

The exact premium-currency payout is derived from the real event payout data and balance simulation. It may scale from the normal repeatable payout, but must remain fully earnable offline.

## Ad conversion

Any path that originally required an advertisement is converted to normal paid-game progression.

Examples:
- ad-gated car -> credit/premium-currency purchase;
- ad reward -> ordinary campaign/race reward;
- ad refill -> remove the artificial gate or use normal gameplay rules.

No fake "ad watched" state should be required.

## Repeat reward rule

The same race may be replayed indefinitely.

For each event:
- completions 1 through 10: **100%** of the normal repeatable reward;
- completion 11 onward: reward drops by **0.2 percentage points per repeat**;
- minimum multiplier: **98%**;
- reward can never drop below 98%, even after hundreds of repeats.

Formula:

```text
repeat_multiplier =
    max(0.98, 1.0 - max(0, repeat_count - 10) * 0.002)
```

Examples:

| Repeat count | Multiplier |
|---:|---:|
| 1-10 | 100.0% |
| 11 | 99.8% |
| 12 | 99.6% |
| 15 | 99.0% |
| 20 | 98.0% |
| 50 | 98.0% |
| 500 | 98.0% |

The same multiplier applies consistently to repeatable normal credits and repeatable premium-currency rewards derived from that race payout.

There must be no hidden reduction based on wallet balance, owned cars, play time, internet state or Microsoft/Gameloft account state.

## Career completion guarantee

A fresh save must be able to finish the offline career without advertisements, real-money purchases, service logins or unreasonable grinding.

For each progression gate:

```text
guaranteed campaign earnings
+ reasonable optional replay earnings
>= required car purchases
+ required upgrades
+ progression expenses
```

The 98% repeat floor ensures every completed event remains a reliable recovery/farming path.

## Saves

Campaign and Sandbox modes use separate save/profile identifiers. Campaign saves store per-event repeat counters so the reward rule is deterministic across restarts.

## Balance workflow

1. extract original shop/career data;
2. apply the 0.20 content-price multiplier;
3. map premium-currency-only items;
4. simulate mandatory car and upgrade gates;
5. apply the repeat-reward rule;
6. ensure premium currency is awarded by races;
7. verify all ad/IAP-only gates have offline replacements;
8. run a fresh-save campaign simulation;
9. play-test conservative, average and completionist spending paths.

The goal is a complete premium-game progression curve, not free/unlimited progression.
