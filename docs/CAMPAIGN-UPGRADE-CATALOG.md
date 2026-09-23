# Campaign Upgrade Catalog

Campaign Edition owns upgrade and pro-kit transactions.

Runtime file:

`_PACKAGE_PHASE5\CampaignUpgrades.dat`

Each entry is keyed by:

`car_id + kind + part_slot + target_level`

Kinds:

- standard upgrade;
- pro kit.

Costs may use:

- credits;
- premium currency;
- Campaign inventory item;
- free/reward upgrade.

The Core requires the car to be owned, the progression gate to be open, and the current level to be exactly one below the requested target. Payment + level mutation + save occur as one Campaign transaction.

The example file is schema documentation only and is never used as a runtime fallback.
