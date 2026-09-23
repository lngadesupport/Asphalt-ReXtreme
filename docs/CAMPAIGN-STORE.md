# Campaign Store

Campaign Store replaces the original monetization/store authority with a local, data-driven system.

Runtime catalog:

`_PACKAGE_PHASE5\CampaignStore.dat`

Each offer defines an offer id, inventory item, quantity, payment type, local price, unlock node and flags.

Supported payment types are credits, premium currency earned in gameplay, and free/reward. Real-money payment and ad completion are not part of this subsystem.

Transaction:

```text
offer_id
  -> CampaignStore.dat
  -> validate unlock node
  -> debit Campaign credits/premium
  -> grant Campaign inventory item
  -> increment save revision
  -> atomically persist CampaignSave.dat
```

If persistence fails, the state snapshot is restored in memory.

Build:

```bat
python tools\build_campaign_store_catalog.py config\campaign_store_catalog.json -o _PACKAGE_PHASE5\CampaignStore.dat
```

The example catalog uses placeholder ids only. Production content must come from Campaign Edition data.
