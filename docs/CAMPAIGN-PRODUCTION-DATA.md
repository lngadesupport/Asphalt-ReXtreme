# Campaign Production Data Builder

This is the authoritative data-generation path for the full Campaign Edition rebuild.

Run from the project root:

```bat
BUILD-CAMPAIGN-PRODUCTION-DATA.cmd
```

It reads the real installed:

`_PACKAGE_PHASE5\data\xml.bin`

and decrypts, in memory:

- `asphaltshop.xtea`;
- `asphaltserverdb.xtea`;
- `career_data.xtea`.

It then generates and installs:

- `CampaignCatalog.dat` — all 61 production vehicles;
- `CampaignEvents.dat` — main-career event/reward graph;
- `CampaignUpgrades.dat` — standard upgrade and pro-kit price schedules.

## Vehicle policy

Direct vehicle acquisition follows real shop data:

- a positive credits price => Campaign credits, at 20% of the original price;
- hardcurrency-only => Campaign premium currency, at 20% of the original price;
- no positive direct price => free/reward acquisition.

Exact-car career gates are used to derive a safe unlock node: the vehicle becomes Campaign-unlocked when the predecessor event for its first mandatory gate is complete.

## Race premium policy

Premium currency is a new offline gameplay reward.

Default per-race premium reward is:

`max(1, round((money_for_playing + position_1) / 2500))`

capped at 5. A zero-credit event awards zero premium.

This is intentionally a Campaign Edition policy, not a claim that the original backend used this formula. It is configurable through CLI arguments.

The runtime repeat decay remains:

- completions 1–10: 100%;
- after 10: -0.2 percentage points per repeat;
- floor: 98%.

## Upgrade/pro-kit policy

The builder reads the actual `UpgradePrices` and `ProKitPrices` records.

If price IDs identify a performance part, that part is retained. If the source contains a shared level schedule, the schedule is replicated across the four performance slots. Positive prices are scaled to 20% and keep their original currency family (credits or hardcurrency -> earnable Campaign premium).

## Guards

The production build refuses to emit a partial vehicle catalog if the decoded shop does not contain the known 61 active cars.

The audit directory contains the decoded source snapshots and JSON rows used for every generated binary.
