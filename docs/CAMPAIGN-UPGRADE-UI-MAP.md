# Campaign Upgrade UI Map

This file is a thin translation layer between preserved upgrade/pro-kit UI actions and Campaign Edition business logic.

Runtime file:

`_PACKAGE_PHASE5\CampaignUpgradeUiMap.dat`

Each entry maps only:

`ui_action_id -> kind + part_slot`

It deliberately does **not** import original request prices, balances, server item semantics, or target levels.

When an adapter submits a UI action, Campaign Core:

1. resolves the UI action to `kind + part_slot`;
2. reads the current Campaign level;
3. computes `target_level = current + 1`;
4. finds the authoritative definition in `CampaignUpgrades.dat`;
5. validates ownership and progression;
6. debits the Campaign resource;
7. applies the new level;
8. persists atomically.

The example identifiers are placeholders and are never a runtime fallback. A production mapping is populated only from verified UI metadata/callsites.
