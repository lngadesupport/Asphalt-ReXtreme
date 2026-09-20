# Offline service map — build 1.7.3.8 x86

This document separates service-only dependencies from Windows/runtime functionality that must remain intact.

## AMS.exe direct imports

### IGPLib_x86.dll

Observed imports include:
- `IGPControl::Init`
- `IGPControl::DestroyIGP`
- `AddIGPComponent`
- `HttpPostLink`
- `ShowIGP`
- `IsOnScreenFreemium`

This library is strongly associated with Gameloft promotion/store/web flows. It is a candidate for **call-site bypass / no-init mode**, not for blind binary deletion.

### WCPToolkit.dll

WCPToolkit mixes online features with essential Windows platform functions.

Online/service-facing imports include:
- in-game browser/news/forum/customer-care;
- reward callback;
- online push notifications;
- Internet connection state;
- advertising ID;
- geolocation.

Essential/local imports include:
- app installed/local folder paths;
- screen width/height and physical resolution;
- gamepad manager;
- system/GPU/CPU/memory information;
- secure/local storage;
- UI-thread helpers.

**Do not remove WCPToolkit.dll wholesale.** ReXtreme should bypass only service-facing initialization/calls while preserving storage, input and display functionality.

## APPX activatable components

The manifest registers:
- `InAppPurchaseComponentW8.dll` / `InAppPurchaseComponentW8.IapComponent`;
- Google Analytics CLR component;
- Vungle/advertising-related runtime components;
- Facebook/MSN runtime classes.

During reverse engineering, component files may remain in the analysis tree so imports and call sites can be classified. The final Campaign runtime must not depend on APPX activation, Store licensing, advertising runtime activation or Microsoft account services.

## Verified service strings / endpoints in AMS.exe

Examples include:
- `scripts/credits/sync.php`
- `scripts/ad_rewards/claim.php`
- `scripts/energy/refill_cc.php`
- `/localprofile`
- `http://vbeta.gameloft.com:20000/locate/asset`
- `https://iap.gameloft.com/freemium/delivery/index.php`
- `https://iap.gameloft.com/freemium/getmanageditems/`
- `https://secure.gameloft.com/freemium/wapbilling/validate.php`
- `http://201205igp.gameloft.com/`
- `gameoptions.gameloft.com`
- `eve.gameloft.com`

Economy/service state strings include:
- `credits_full_sync`, `credits_partial_sync`;
- `hardcurrency_full_sync`, `hardcurrency_partial_sync`;
- `ad_rewards_full_sync`;
- `playerCachedHardCurrency`;
- `creditsEarnedToday`;
- `DoubleCreditsLimit_%d`;
- `DoubleCreditsRaceLimit_%d`.

These are targets for further xref/call-graph analysis. They are **not yet patch offsets**.

## Local profile

The client contains explicit `localprofile` / `/localprofile` strings and WCP local-folder/storage APIs. This supports the goal of retaining profile state locally while disconnecting remote sync.

## Campaign implementation order

1. Inventory PE imports and WinRT/package activation on the exact supported build.
2. Classify mixed-purpose platform calls so display/input/local storage remain intact.
3. Bypass IGP, Store, IAP, social and advertising initialization/call sites.
4. Replace package-family save paths with Campaign-owned local paths.
5. Prevent credit, hardcurrency, ad-reward and energy operations from requiring remote sync.
6. Preserve local profile/save writes and validate atomic persistence.
7. Remove APPX/package metadata from the final portable output only after package identity is no longer required.
8. Validate with Internet enabled and Microsoft Store still signed in.

Campaign Edition does not use APPX installation as a compatibility fallback.

## Central connectivity flag / Offline Alpha

The verified client singleton contains a connectivity byte at `+0x4B0`. Getter VA `0xFAD9D0` is:

```asm
mov al, byte ptr [ecx+0x4B0]
ret
```

It has **211 direct call sites**. Static tracing shows a false value skips OnlinePush initialization and selects the offline branch in connection update logic.

Experimental target for build 1.7.3.8 x86:

```text
AMS.exe SHA-256:
3d48800d37cb799e424abe5e33e07bab3235d11dbfbe2fbf50214cecab3e75c8

file offset: 0xBACDD0
before: 8A 81 B0 04 00 00 C3
after:  31 C0 C3 90 90 90 90
```

The replacement becomes `xor eax,eax; ret` plus padding. Re-disassembly is valid and the patched Alpha binary hashes to:

```text
a446fec5ad65bf26fefede70453b302be81fd3d7024e655183bf810c3618176f
```

Status: **Offline Alpha / runtime test required**.
