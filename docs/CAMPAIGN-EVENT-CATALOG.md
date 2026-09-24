# Campaign Event Catalog

Campaign Edition owns post-race rewards and progression.

Runtime file:

`_PACKAGE_PHASE5\CampaignEvents.dat`

The original race engine, physics, race AI, controls, renderer and in-race HUD remain untouched. The event catalog begins only at the result boundary.

Each entry contains:

- event id;
- required Campaign progression node;
- completion node;
- participation credits;
- 1st/2nd/3rd-place credit bonus;
- repeatable premium-currency reward;
- maximum stars;
- flags.

The catalog is sorted, fixed-size and FNV-1a checksum protected.

The example catalog contains placeholders only. Production event data must be generated from the decoded career data; runtime never falls back to placeholders.
