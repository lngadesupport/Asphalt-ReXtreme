# Verified findings — Windows build 1.7.3.8 x86

## Build identity

- Original package: `A278AB0D.AsphaltXtreme`
- Version: `1.7.3.8`
- Architecture: x86
- Original entry point: `AMS.exe` / `AMS.App`
- Original platform model: Microsoft Store APPX
- Core original dependency: `Microsoft.VCLibs.120.00`

## Service / monetization components

Static analysis previously identified:
- `InAppPurchaseComponentW8.dll`;
- `IGPLib_x86.dll`;
- `WCPToolkit.dll`;
- `Microsoft.Live.dll`;
- `Facebook.dll`.

The client also contains local profile/save, career, currency, reward and upgrade logic. Campaign Edition therefore targets local replacement/bypass of commercial service dependencies rather than recreation of the original services.

## Mixed-purpose platform code

`WCPToolkit.dll` contains both service-facing and useful local Windows functionality such as display/input/storage helpers. It must not be deleted blindly. Calls are classified before replacement.

## Data archive

`data/xml.bin` contains encrypted/configuration assets, including:
- `asphaltshop`;
- `career_data`;
- `asphaltserverdb`;
- request/service metadata.

The XTEA tooling in this repository can decode/repack the relevant data path.

## Economy target

Campaign Edition supersedes the previous 0.80 experiment.

Normal shop content target:

```text
campaign_price = round(original_price * 0.20)
```

Race repetition target:

```text
runs 1-10: 100%
run 11+: -0.2 percentage points per repeat
floor: 98%
```

Premium currency is earned from race rewards and is not dependent on Store purchase.

## Offline connectivity patch

The verified client singleton connectivity getter at file offset `0xBACDD0` was previously identified as a useful offline experiment. That patch is still relevant to legacy service suppression, but Campaign Edition additionally requires removal/replacement of Microsoft package identity, Store/IAP/auth activation and package-dependent save/runtime paths.

## Current next step

Run `tools/store_dependency_audit.py` against the extracted full source build, then classify every Microsoft/package finding as:
- remove/bypass;
- replace with local Win32/path/save behavior;
- retain only if it is generic Windows functionality unrelated to Store/package identity.
