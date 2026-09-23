# Campaign Edition — Full Rebuild Boundary

## Project rule

Campaign Edition replaces **all game/service/business logic** unless it belongs to one of the explicitly preserved engine/presentation subsystems below.

This is the literal architectural boundary for the revival.

## Preserved subsystems

The following original systems are retained and are not targets for replacement:

1. race physics;
2. race AI;
3. renderer;
4. 3D models;
5. animations;
6. audio;
7. track loading;
8. controls;
9. in-race HUD;
10. visual garage UI.

These are treated as the legacy engine/presentation layer.

The garage UI may be used as a visual and input surface, but its original business logic is not authoritative.

## Replaced subsystems

Everything outside the preserved list is owned by Campaign Edition.

### Core state

- profile;
- save format;
- save migration;
- local persistence;
- revisions/versioning;
- backup/recovery;
- ownership;
- active/selected vehicle state;
- player progression;
- unlock state.

### Economy

- credits;
- premium currency;
- blueprint balances;
- parts/material inventory;
- boosters;
- pro kits;
- purchase validation;
- reward payouts;
- upgrade costs;
- acquisition costs;
- economy tables.

### Vehicle lifecycle

- vehicle acquisition;
- local CraftCar replacement;
- blueprint crafting;
- direct purchase;
- ownership queries;
- upgrade levels;
- pro-kit progression;
- vehicle unlock requirements;
- garage action routing.

### Campaign/progression

- chapters;
- seasons/career nodes;
- race unlock requirements;
- stars;
- objective completion;
- post-race progression;
- event completion;
- reward claiming;
- difficulty/progression gates.

### Events

- offline event definitions;
- event state;
- local event scheduler;
- permanent/rotating challenges;
- event rewards;
- event unlock rules;
- event completion persistence.

### Race result layer

The original race simulation remains untouched.

Campaign Edition owns what happens **after** the engine produces race results:

- placement;
- finish time;
- objective evaluation;
- stars;
- credits;
- premium currency;
- blueprint drops;
- progression unlocks;
- statistics;
- persistence.

### Online/service replacement

The following original service paths are retired from Campaign Edition:

- Gameloft backend;
- CraftCar backend;
- remote profile;
- remote inventory;
- server ownership;
- server economy;
- server event synchronization;
- server reward synchronization;
- remote JSON gameplay responses;
- IAP;
- ads;
- IGP runtime gameplay dependencies;
- login-dependent gameplay gates;
- online-only progression gates.

### Store/monetization

Original monetization semantics are removed.

Campaign Edition provides local equivalents for:

- car purchase;
- upgrades;
- boosters;
- pro kits;
- premium-currency earning;
- formerly ad-gated content;
- formerly IAP-gated content.

## Architecture

```text
+-------------------------------------------------------+
|                 ORIGINAL ENGINE LAYER                 |
|                                                       |
| physics | AI | renderer | models | animations | audio |
| track loading | controls | race HUD | garage visuals  |
+---------------------------+---------------------------+
                            |
                     thin UI/game adapters
                            |
+---------------------------v---------------------------+
|                 CAMPAIGN EDITION CORE                 |
|                                                       |
| CampaignProfile        CampaignInventory              |
| CampaignEconomy        CampaignCraft                  |
| CampaignGarage         CampaignProgression            |
| CampaignEvents         CampaignRewards                |
| CampaignRaceResults    CampaignUpgrades               |
| CampaignProKits        CampaignVehicleUnlock          |
| CampaignPersistence    CampaignSaveMigration          |
| CampaignAPI            CampaignDiagnostics            |
+---------------------------+---------------------------+
                            |
                            v
                    CampaignSave.dat
```

## Garage rule

The original garage visual UI is preserved.

The original garage business logic is not.

The intended path is:

```text
original MONTAR button
        |
        v
CampaignGarageController
        |
        +--> CampaignAPI.GetSelectedCar()
        +--> CampaignAPI.CanAcquire()
        +--> CampaignAPI.Craft()/Purchase()
        +--> CampaignPersistence.Save()
        +--> visual refresh adapter
        |
        X  no original CraftCar/backend/event sync
```

Original CraftCar code is considered retired.

The following original paths must not be used as gameplay authorities:

- `CraftCar_Caller`;
- `CraftCarRequestImpl`;
- `CraftCar_Result`;
- `CraftCar_ResultApply`;
- original CraftCar observers/listeners;
- original backend-owned inventory;
- original backend-owned ownership state.

## Race rule

The race itself remains original.

```text
original physics/AI/controls/render/HUD
                 |
                 v
          race result adapter
                 |
                 v
      CampaignRaceResults
                 |
        +--------+---------+
        |        |         |
     rewards  progress  statistics
        |        |         |
        +--------+---------+
                 |
                 v
          CampaignSave.dat
```

## API rule

Binary integration should converge on one stable interface rather than scattered gameplay patches.

Representative API:

```cpp
Campaign_IsCarOwned(car_id);
Campaign_CanAcquireCar(car_id);
Campaign_AcquireCar(car_id);

Campaign_GetCredits();
Campaign_AddCredits(amount);
Campaign_SpendCredits(amount);

Campaign_GetPremiumCurrency();
Campaign_AddPremiumCurrency(amount);
Campaign_SpendPremiumCurrency(amount);

Campaign_GetBlueprints(blueprint_id);
Campaign_AddBlueprints(blueprint_id, amount);
Campaign_SpendBlueprints(blueprint_id, amount);

Campaign_GetUpgradeLevel(car_id, part);
Campaign_Upgrade(car_id, part);

Campaign_GetProKitLevel(car_id, part);
Campaign_ApplyProKit(car_id, part);

Campaign_RecordRace(result);
Campaign_GetProgression(node_id);
Campaign_ClaimReward(reward_id);

Campaign_Save();
Campaign_Load();
```

## Data ownership rule

Campaign Edition data is the source of truth.

Original game data may still be read for presentation/engine metadata where useful (for example car identifiers, display assets, race/track identifiers), but original online/service state is never authoritative.

## Integration rule

Original code is permitted only in three roles:

1. preserved engine/presentation systems;
2. read-only metadata/source identifiers needed to bind the new systems to existing assets;
3. thin UI/engine adapters.

It must not remain the authority for any replaced subsystem.

## Current implementation direction

The clean-room Campaign Runtime V2 already establishes:

- independent ownership;
- independent blueprint inventory;
- independent craft transaction;
- independent persistence;
- independent event bus;
- garage action routing.

Next integration work should proceed in this order:

1. redirect garage build/purchase actions to Campaign Runtime V2;
2. redirect garage ownership reads to CampaignProfile;
3. add visual refresh adapter without changing garage visuals;
4. add full CampaignSave schema;
5. bind local economy tables;
6. replace upgrades/pro kits;
7. replace post-race rewards/progression;
8. replace event/progression systems;
9. remove remaining online/service dependencies;
10. perform full regression against the ten preserved subsystems.

## Non-goal

The project does **not** seek to rewrite the race engine or visual asset pipeline.

The target is a new offline game/service layer running on top of the preserved Asphalt Xtreme engine and presentation stack.
