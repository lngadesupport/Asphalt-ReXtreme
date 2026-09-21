# Campaign Edition — portable Win32 architecture

## Decision

The primary release is now **Asphalt ReXtreme: Campaign Edition**.

The release must behave like a normal portable Windows racing game. It must not require or use Microsoft Store deployment, APPX/MSIX registration, AppUserModelID activation, Microsoft account authentication, Store licensing, Xbox authentication, or Store IAP.

Target user flow:

```text
Asphalt ReXtreme Campaign Edition/
├── AsphaltReXtreme.exe
├── GameData/
├── config/
├── save/
├── logs/
└── runtime/
```

The user extracts the folder and launches `AsphaltReXtreme.exe`.

Internet may be enabled and the user may remain signed into Microsoft Store. Campaign Edition must simply ignore those services.

## Non-goals

Campaign Edition will not:
- log the user out of Microsoft Store;
- disable networking;
- alter Windows Store, Xbox or Windows system configuration;
- install/register an APPX/MSIX package;
- emulate a Microsoft Store license;
- require Developer Mode, sideload policy, certificate installation or Add-AppxPackage;
- redirect the original Store package identity.

## Runtime separation

The original 1.7.3.8 x86 build is treated as four layers:

1. **Game engine / rendering / audio / input**
2. **Local game data / career / garage / profile**
3. **Gameloft online services / advertising / IAP**
4. **Microsoft package identity / Store / UWP activation**

Campaign Edition preserves layers 1 and 2 wherever possible, replaces layer 3 with local paid-game behavior, and removes or replaces layer 4.

## Entry point

The final entry point is a normal desktop executable:

```text
AsphaltReXtreme.exe
    -> initialize portable runtime
    -> load local profile
    -> load local game data
    -> create normal Windows game window
    -> enter campaign
```

No launcher action may invoke `ms-windows-store:`, `Add-AppxPackage`, App Installer, PackageManager deployment, or AppUserModelID activation.

## Local profile

Campaign Edition owns its save path and profile identity.

Required persisted state:
- credits;
- premium currency;
- cars;
- paints/customization;
- upgrades;
- career stars and completion;
- race records;
- settings;
- per-event repeat counters used by the reward floor rule.

Writes should be atomic and recoverable. Keep at least one previous-save backup.

## Economy contract

The authoritative machine-readable policy is `config/campaign_economy.json`.

- Standard career races: **2,500–5,000 credits**, rank-scaled, plus **2–5 tokens per completed secondary objective**.
- Boss/season-final races: **15,000–25,000 credits + 50 tokens**.
- Player level-up: **100–250 tokens + a guaranteed parts pack**.
- Part resale: common **500**, uncommon **2,000**, rare **5,000**, epic **15,000** credits.
- Vehicle prices preserve relative order within class:
  - D: **25,000–75,000 credits**;
  - C: **150,000–300,000 credits**;
  - B: **500,000–800,000 credits** or **500 tokens**;
  - A: **1,200,000–2,000,000 credits** or **1,500 tokens**;
  - S: **3,000,000+ credits** or **3,500+ tokens**.
- Upgrade costs per attribute:
  - levels 1–2: **2,000–8,000 credits**;
  - levels 3–4: **15,000–40,000 credits**;
  - level 5 / PRO: **75,000–150,000 credits**, plus appropriate class parts.
- Local reward boxes:
  - basic: **10,000 credits**;
  - advanced: **50,000 credits**;
  - premium: **75–150 tokens**.
- Currency packs / real-money products are removed from progression.
- Ads are never required; ad-gated rewards/content become local campaign rewards or purchases.
- Repeating the same race:
  - runs 1–10: 100% reward;
  - run 11 onward: -0.2 percentage points per additional repeat;
  - floor: 98%.
- No hidden reward reduction based on wallet balance, ownership, play time or network state.

```text
repeat_multiplier = max(0.98, 1.0 - max(0, repeat_count - 10) * 0.002)
```

## Microsoft-free acceptance test

Campaign Edition is accepted only when all of the following are true:

1. Windows 10/11 user remains signed into Microsoft Store.
2. Internet remains enabled.
3. Original Asphalt Xtreme Store package is not required to be installed.
4. Double-clicking `AsphaltReXtreme.exe` opens the game directly.
5. No Store, App Installer, Xbox login, package registration or license dialog appears.
6. No Microsoft account is required.
7. Campaign can start and finish races.
8. Credits and premium currency are awarded locally.
9. Shop purchases persist locally.
10. Closing and reopening the game preserves progress.
11. Network availability does not change the local campaign behavior.

## Development rule

Do not delete mixed-purpose platform DLLs blindly. First identify which calls are Store/service-facing and which provide essential local Windows functionality. Replace or bypass only the service/package-facing paths until a native equivalent exists.
