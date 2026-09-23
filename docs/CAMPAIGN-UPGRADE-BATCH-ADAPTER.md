# Campaign Upgrade Batch Adapter

Campaign Edition treats the preserved upgrade UI as an input surface only.

The original `upgrade_car.php` request, request balances and request prices are not authoritative.

## Gateway

Selector:

`0xC0DE4401`

The patched AMS adapter passes a pointer in `ECX` to:

```c
#define CAMPAIGN_UPGRADE_BATCH_MAX 16u

typedef struct CampaignUpgradeBatchArgs {
    uint32_t size;
    int32_t car_id;
    uint32_t count;
    int32_t ui_action_ids[CAMPAIGN_UPGRADE_BATCH_MAX];

    int32_t status;
    int32_t applied_count;
    uint32_t revision;
} CampaignUpgradeBatchArgs;
```

## Transaction

For every visual action id:

1. resolve `ui_action_id` through `CampaignUpgradeUiMap.dat`;
2. obtain Campaign `kind + part_slot`;
3. calculate `target_level = current + 1`;
4. resolve the price/gate through `CampaignUpgrades.dat`;
5. debit Campaign credits/premium/inventory;
6. mutate Campaign upgrade/pro-kit level.

All selected ids are applied in one state snapshot and one save commit.

If any selected id, payment, progression gate or persistence operation fails, the entire batch is rolled back.

Duplicate ids in the same batch are rejected to prevent accidental double-leveling.

## Read-only legacy metadata

The old manager selection list is permitted only as a source of stable visual ids.

Verified legacy facts:

- selected entries are 8 bytes each;
- the first dword is the raw id;
- the same raw id was historically serialized as `up_id`, `bp_id` or `tu_id`;
- `0x0099D120(raw_id)` returns the legacy visual/content type.

Campaign Edition does **not** use the original balance, price or backend fields.

## Production target

```text
preserved upgrade UI
       |
       +--> selected car id
       +--> selected raw visual ids
       |
       v
CampaignUpgradeBatchArgs
       |
       v
selector 0xC0DE4401
       |
       v
Campaign Core
       |
       +--> CampaignUpgradeUiMap.dat
       +--> CampaignUpgrades.dat
       +--> CampaignSave.dat
       |
       v
preserved visual refresh
```

The original `UpgradeCarRequestImpl` becomes unreachable from the user action after the AMS adapter is installed.
