# Campaign Core v2 — Production Authority

Campaign Core v2 is the production foundation for the literal Campaign Edition rebuild.

## Runtime safety

The runtime remains:

- x86;
- `/NOENTRY`;
- `/NODEFAULTLIB`;
- no CRT;
- no C++ runtime;
- no startup thread;
- no `DllMain`;
- no secondary `LoadLibrary`.

Nothing executes simply because `IGPLib_x86.dll` was loaded.

The DLL exists only because the original executable already imports that module. One unused IGP import is repurposed as an explicit command gateway when Campaign Edition patched call sites invoke it.

## Authority

Campaign Core v2 owns:

- credits;
- premium currency;
- generic inventory;
- blueprints through inventory ids;
- car ownership;
- local crafting transactions;
- upgrades;
- pro-kit levels;
- campaign node progress;
- race counters/rewards;
- state revision;
- persistence and backup recovery.

Original CraftCar/backend/profile/inventory state is not authoritative.

## Save

Primary:

`%LOCALAPPDATA%\Packages\A278AB0D.AsphaltXtreme_h6adky7gbf63m\LocalState\CampaignEdition\CampaignSave.dat`

Backup:

`CampaignSave.bak`

Temporary transactional file:

`CampaignSave.tmp`

Writes use a replace sequence. The previous valid save is retained as `.bak`.

The loader tries, in order:

1. `CampaignSave.dat`;
2. `CampaignSave.bak`;
3. v1 `campaign_state.bin` migration;
4. a new default Campaign save.

## v1 migration

The v1 Campaign state is migrated automatically once. Preserved fields:

- revision;
- credits;
- premium currency;
- craft count;
- owned cars;
- inventory entries;
- last acquired car.

New v2 tables start empty.

## Command ABI

Patched AMS adapters call the already-imported IGP gateway with selector:

`0xC0DECA11`

and pass a pointer to `CampaignCommand` in `ECX`.

This keeps the DLL import/bootstrap surface minimal while providing one stable API.

Supported operations:

- credits get/add/spend;
- premium currency get/add/spend;
- inventory get/add/spend;
- ownership query/acquire;
- atomic local craft;
- upgrade get/set;
- pro-kit get/set;
- progression get/set;
- race reward recording;
- save/reload.

## Atomic craft

`CAMPAIGN_OP_CRAFT_CAR` takes:

- `a = car_id`
- `b = blueprint/item_id`
- `c = blueprint_cost`

The transaction is:

1. reject invalid recipe;
2. return success if already owned;
3. snapshot entire Campaign state;
4. verify and debit inventory;
5. add ownership;
6. increment craft count/revision;
7. persist;
8. rollback in memory if persistence fails.

No original CraftCar code participates.

## Preserved systems

Campaign Core v2 does not replace or modify the project-preserved engine/presentation systems:

1. physics;
2. race AI;
3. renderer;
4. models;
5. animations;
6. audio;
7. track loading;
8. controls;
9. in-race HUD;
10. visual garage UI.

The garage is an input/rendering adapter only.
