# Campaign UI Adapter Map v1

This document records only call sites verified in the x86 Asphalt Xtreme 1.7.3.x client used by Campaign Edition.

## Garage

Already integrated:

- `GS_Garage::BuildCar` entry: `0x00A87960`
- selected-car id helper: `0x00D805F0`
- Campaign ownership membership replacement: `0x00E530E0`

The old CraftCar path is not authoritative.

## Pro-kit / vehicle upgrade request path

Verified from the binary:

- `UpgradeCarRequestImpl` RTTI decorated name: `.?AVUpgradeCarRequestImpl@prokitsv2@@`
- primary vftable: `0x01840D88`
- secondary vftable: `0x01840DB0`
- constructor-like routine assigning those vtables: `0x009AA690`
- single direct caller of that constructor: `0x009995AD`
- request-creation wrapper containing that call: starts at `0x009994F0`
- manager submit function: `0x009A0930`
- verified UI-side caller of the manager submit function: `0x00951658`

At `0x00951648`, the UI path calls the known selected-car id helper `0x00D805F0` and pushes the returned car id immediately before invoking `0x009A0930`.

The original request implementation later builds the URL:

`scripts/cars/upgrade_car.php`

and serializes legacy fields including:

- `car_id`
- `levelup`
- `up_id`
- `up_balance`
- `up_price`
- `tu_id`
- `tu_balance`
- `tu_price`

Campaign Edition will not reproduce that request. The purpose of mapping it is to identify the UI action boundary before the legacy request is created.

### Current adapter status

`car_id` extraction is proven.

The exact Campaign mapping of the UI action argument at the handler boundary to:

- Campaign `part_slot`;
- Campaign `target_level`;
- standard upgrade vs pro-kit;

is still being decoded. No patch should guess those values.

## End-race career UI

Verified RTTI:

- `GS_EndRaceScreenResultsCareer`
- primary vftable: `0x0181F5C8`

Related result base:

- `GS_EndRaceScreenResults`
- primary vftable: `0x0186C278`

Campaign Edition now has a separate transactional race lifecycle in the Core. These classes are candidates only for thin begin/finish adapters; their original reward/progression logic is not authoritative.

## Reverse-engineering tooling

Use:

```bat
python tools\campaign_msvc_rtti_map.py _PACKAGE_PHASE5\AMS.exe ^
  GS_ProkitsDetails ^
  prokitsv2::UpgradeCarRequestImpl ^
  GS_EndRaceScreenResultsCareer
```

The mapper reads x86 MSVC TypeDescriptor / CompleteObjectLocator / vftable relationships and returns executable method addresses without requiring debug symbols.


## Correction: GarageUpgradeWidget +0x14

Verified direct callers of `GarageUpgradeWidget::0x00978B50`:

- `0x00978E97`
- `0x00AD3A15`

The caller at `0x00AD3A15` resolves the currently selected car with `0x00D805F0` and pushes that returned value directly into `0x00978B50`.

Therefore:

`GarageUpgradeWidget + 0x14 = car_id`

It is **not** a part slot, target level or legacy upgrade item id.

The second caller at `0x00978E97` simply reuses the widget's own `+0x14`, consistent with the same interpretation.

## Upgrade action abstraction

Because the legacy request serializes multiple unrelated ids (`up_id`, `bp_id`, `tu_id`) and does not expose a clean part-slot ABI, Campaign Edition now uses:

`CampaignUpgradeUiMap.dat`

The preserved UI adapter will submit only:

- Campaign `car_id`;
- verified visual `ui_action_id`.

Campaign Core resolves that id to:

- standard upgrade or pro-kit;
- Campaign `part_slot`.

It then computes `target_level = current Campaign level + 1` and resolves cost/gates from `CampaignUpgrades.dat`.

No original request price/balance fields become Campaign authority.


## Post-race Career adapter — verified raw result sources

Campaign Edition keeps the race engine and result presentation, but owns stars, rewards and progression.

### Event id

The active event id is obtained through `0x00CBFC20`:

```asm
mov eax,[ecx+0xC0]
mov eax,[eax]
ret
```

That returned value is subsequently used as the key into the event-definition table rooted at `0x0193B700` (entry stride `0x220`) and in the `STR_EVENT_DEF_%s` presentation path.

The Career telemetry producer `0x00F0E070` independently writes the same value to its output `event_id` field at `+0x20`.

Therefore this value is the verified event identifier for the post-race adapter.

### Placement

Inside `0x00F0E070`, the active race object is queried through virtual slot `+0x40`. The return value is passed to `0x00F66D20`.

`0x00F66D20` accepts placements 1 through 7 and only converts them to the legacy telemetry result enum. Campaign Edition must capture the raw 1-based placement before that conversion.

### Player race time

The raw player timer is stored encrypted/obfuscated at race-controller offset `+0x98`.

The original producer decodes it as:

```text
raw_ms = *(u32*)(controller + 0x98)
         XOR address(controller + 0x98)
         XOR *(u32*)0x0193A1C8
```

The original telemetry code then converts that integer to float and divides by the constant at `0x01662F7C`, which is `1000.0f`, before rounding. This proves that the decoded raw field is milliseconds.

Campaign Edition should submit the decoded integer directly as `finish_time_ms`; it must not reuse the rounded telemetry seconds.

### General raw metric telemetry layout

The general race telemetry serializer `0x00F6B490` exposes the following output fields produced by `0x00F0D880`:

| Offset | Metric |
|---:|---|
| `+0x04` | avg_speed |
| `+0x08` | car_used |
| `+0x0C` | car_used_level |
| `+0x10` | km_made |
| `+0x14` | m_drifted |
| `+0x18` | race_mode |
| `+0x1C` | race_time_first |
| `+0x20` | race_time_player |
| `+0x24` | race_type |
| `+0x28` | time_air |
| `+0x2C` | time_in_nitro |
| `+0x30` | times_break_obs |
| `+0x34` | times_jump_flat |
| `+0x38` | times_jump_normal |
| `+0x3C` | times_jump_roll |
| `+0x40` | times_nitro_allin |
| `+0x44` | times_nitro_chain |
| `+0x48` | times_nitro_normal |
| `+0x4C` | times_out |
| `+0x50` | wrecked_cars |
| `+0x54` | wrecked_environment |
| `+0x58` | wrecks_made |

These are output-structure offsets, not yet proven source-object offsets. The final adapter must read the underlying engine counters, not depend on the telemetry serializer itself.

### Career telemetry layout

The Career producer `0x00F0E070` and serializer `0x00F6C3B0` expose:

- `+0x20 event_id`;
- `+0x38 result`;
- `+0x3C result_param`;
- reward metadata at `+0x40..+0x5C`;
- `+0x60 season`;
- `+0x64 soft_currency_earned`;
- `+0x68/+0x6C/+0x70 star_1/2/3_achieved`;
- `+0x74 all_stars_achieved`;
- `+0x78 time_spent`;
- `+0x7C series_type`.

The original star booleans are reverse-engineering validation only. The production Campaign path evaluates `CampaignObjectives.dat` from raw race metrics through `CAMPAIGN_OP_FINISH_EVENT_RACE_METRICS`.

### Production boundary

The intended final adapter is:

```text
preserved race engine
       |
       +--> verified event id
       +--> raw placement
       +--> raw time/counters
       |
       v
CampaignRaceMetrics
       |
       v
CAMPAIGN_OP_FINISH_EVENT_RACE_METRICS
       |
       +--> CampaignObjectives.dat
       +--> local stars
       +--> CampaignEvents.dat
       +--> local rewards/progression
       +--> CampaignSave.dat
       |
       v
preserved result UI
```

The legacy upload/synchronization logic in `GS_EndRaceScreenResultsCareer` is not Campaign authority.
