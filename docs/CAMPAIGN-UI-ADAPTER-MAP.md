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
