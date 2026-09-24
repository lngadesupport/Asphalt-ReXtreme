# Campaign Store Key Audit

`tools/audit_campaign_store_keys_from_package.py` is a discovery tool for the generic legacy shop.

It scans the extracted package for files that contain known purchase markers such as:

- `scripts/general/buy_item.php`;
- `item=`;
- `OnlinePurchaseRequest`.

It then reports textual content keys that look like locally purchasable items.

The output is **not** a runtime catalog. This is deliberate.

A discovered key becomes a `CampaignStore.dat` offer only after Campaign Edition has verified or explicitly defined:

- resulting `item_id`;
- quantity;
- local currency;
- local price;
- progression gate.

This prevents reverse-engineering guesses from silently becoming economy rules.
