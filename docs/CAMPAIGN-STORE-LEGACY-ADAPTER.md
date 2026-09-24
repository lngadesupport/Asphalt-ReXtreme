# Campaign Store Legacy Adapter

Campaign Edition uses the preserved shop UI only as an input/presentation surface.

The legacy online serializer at `0x00A521F0` proves the local purchase path uses:

- endpoint `scripts/general/buy_item.php`;
- literal `item=`;
- a stable zero-terminated item key obtained from the local purchase context.

Verified read-only layout:

```text
PurchaseRequestContext + 0x08 -> item object
item object            + 0x0C -> const char* item_key
```

Campaign Edition does not use the legacy price, currency balance, backend response, or OnlinePurchaseResult as authority.

## Stable local offer id

The item key is converted to a deterministic 31-bit FNV-1a id:

```text
offer_id = FNV1a_UTF8(item_key) & 0x7fffffff
```

Zero is remapped to one.

`build_campaign_store_catalog.py` accepts either:

- explicit `offer_id`; or
- `offer_key`, from which the same id is generated.

Hash collisions are rejected at catalog build time.

## Gateway

Selector:

`0xC0DE5501`

Input:

`CampaignLegacyStoreArgs*`

The Core:

1. reads only the stable local item key;
2. derives the local offer id;
3. resolves `CampaignStore.dat`;
4. validates progression/payment;
5. grants the Campaign inventory item;
6. persists atomically.

UI completion/refresh is intentionally kept outside this adapter so legacy shop business logic cannot re-enter the authority path.
