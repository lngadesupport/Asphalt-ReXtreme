# Campaign Vehicle Catalog

The Campaign Vehicle Catalog is the authoritative acquisition table for the rebuilt game layer.

It is independent of CraftCar, server inventory and remote economy responses.

Runtime file:

`_PACKAGE_PHASE5\CampaignCatalog.dat`

The no-CRT Campaign Core loads it from the same directory as `IGPLib_x86.dll`.

Each vehicle entry contains:

- `car_id`;
- acquisition type;
- blueprint/item id when relevant;
- acquisition cost;
- Campaign unlock node;
- class id;
- flags.

Acquisition types:

1. blueprint;
2. credits;
3. premium currency;
4. free/unlock reward.

The binary catalog is sorted by `car_id` and checksum-protected.

Source catalogs may be authored as JSON/CSV and compiled with:

```bat
python tools\build_campaign_vehicle_catalog.py config\campaign_vehicle_catalog.json -o _PACKAGE_PHASE5\CampaignCatalog.dat
```

The example file intentionally uses placeholder IDs and is **not** production balance data.
No placeholder recipe is automatically used at runtime.
