# Premium economy implementation status

## Current 1.0 RC rule

The 1.0 RC uses the paid-game Premium model approved for ReXtreme:

- every positive vehicle purchase price is reduced to exactly **80%** of its original value;
- the vehicle's original purchase currency is preserved;
- credit-priced cars remain credit-priced;
- hardcurrency-only cars remain Premium-currency cars;
- every completed race grants Premium currency equal to
  `floor(repeatable_credit_payout × 0.50)`;
- repeatable payout means `money_for_playing + finishing-position reward`;
- repeating an event must not reduce either payout;
- normal career/season hardcurrency rewards are also preserved as Premium currency.

This replaces the earlier Phase-1 idea of zeroing an alternative hardcurrency price or converting all hardcurrency-only cars into credits.

## Why this model is preferable

The main career contains mandatory cars that were hardcurrency-only in the original build. Converting them all to credits with a class-derived exchange rate produced an economy far above the career's available credit flow.

ReXtreme instead turns hardcurrency into an earnable gameplay currency. This keeps two meaningful progression currencies without real-money purchases, ads, login, or servers.

## Data patch

`tools/make_premium_shop.py` applies the 0.80 multiplier to every positive
`CAR_PRICE` in the shop data while preserving the currency type.

The modified plaintext can be written back into `data/xml.bin` using the
validated type-0 stream path in `tools/repack_xmlbin.py`. The repacker keeps
the original entry sizes and offsets, so `xml.bin.hdr` remains compatible.

## Progression simulation

`tools/economy_simulator.py` now models the actual two-wallet system:

- each new race increases credits by its normal/one-time career rewards;
- it increases Premium currency by 50% of the repeatable payout;
- season hardcurrency rewards increase the Premium wallet;
- a mandatory credit car spends credits;
- a mandatory Premium car spends Premium currency;
- if a gate is unaffordable, the simulator calculates repeat races using the
  best previously available repeatable event and credits both currencies for
  each simulated replay.

A candidate economy is not accepted for 1.0 if a mandatory gate is impossible
from a fresh save. Farming counts will also be reviewed manually: technically
possible progression is not enough if the result is still grind-heavy.

## Remaining 1.0 work

Upgrade costs, blueprint/card acquisition, and any non-purchase car unlock
conditions still require runtime validation. Premium mode will not solve those
unknowns by silently granting unlimited currency; unrestricted behavior belongs
in the separate Sandbox mode.
