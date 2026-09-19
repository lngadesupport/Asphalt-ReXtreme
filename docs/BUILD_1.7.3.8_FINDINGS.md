# Verified findings — Windows build 1.7.3.8 x86

## Build identity

- Package: `A278AB0D.AsphaltXtreme`
- Version: `1.7.3.8`
- Architecture: x86
- Entry point: `AMS.exe` / `AMS.App`
- Core dependency: `Microsoft.VCLibs.120.00`

The manifest declares Internet client, private-network client/server and
location capabilities.

## Service / monetization components

Static analysis identifies old Gameloft IAP, advertising/cross-promotion and
social endpoints, plus imports from:

- `InAppPurchaseComponentW8.dll`;
- `IGPLib_x86.dll`;
- `WCPToolkit.dll`;
- `Microsoft.Live.dll`;
- `Facebook.dll`.

The client itself contains local profile/save, career, currency, energy,
reward and upgrade logic. ReXtreme therefore targets removal or replacement of
obsolete service validation instead of recreating the original commercial
services.

## Graphics configuration

`Gameoptions_W8.json` contains frame-rate and resolution settings. The
observed default action/menu cap is 60 FPS, with a 30 FPS override for a lower
GPU preset. Higher limits must be tested for timing/physics correctness before
being enabled as release defaults.

## Data archive

`data/xml.bin` is a ZIP archive containing 59 encrypted `.xtea` assets.
The XTEA format has been fully reproduced; see `XTEA_FORMAT.md`.

Important decoded assets include:

- `asphaltshop`: vehicle/shop and upgrade prices;
- `career_data`: career events, seasons, payouts and requirements;
- `asphaltserverdb`: vehicle definitions/classes/base ranks;
- `request_rate`: request metadata/rate configuration.

## Economy inventory

The target shop contains 61 vehicles:

- 31 with both credit and hard-currency prices;
- 29 hard-currency-only;
- 1 credit-only.

For vehicles that already have a credit price, ReXtreme Premium uses the
agreed exact baseline:

`new_credit_price = round(original_credit_price * 0.80)`

Token-only vehicles are **not** converted using one global exchange rate.
The observed credit/token ratios of dual-priced cars vary too widely. Their
Premium credit prices will be derived from class, base rank and career
progression so they remain attainable without flattening progression.

## Career payouts

`career_data` contains explicit fields such as `money_for_playing`,
`position_1`, `position_2`, `position_3`, star rewards and season
completion rewards.

A first implementation candidate for a normal repeatable first-place payout is
`money_for_playing + position_1`. This interpretation still requires runtime
verification before it becomes a patch rule. ReXtreme's design requirement
remains that repeating an event never reduces its normal payout.
