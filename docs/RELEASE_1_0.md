# Asphalt ReXtreme Offline Edition — 1.0 Release Gate

Version 1.0 is a **full ReXtreme repack** derived locally from the verified Asphalt Xtreme 1.7.3.8 x86 source.

## 1.0 identity

- Package name: `ReXtreme.AsphaltXtreme`
- Display name: `Asphalt ReXtreme`
- Version: `1.0.0.0`
- Original Store package identity is not reused.
- ReXtreme uses its own signing identity and installer.

## Core gameplay gates

A 1.0 build must pass all of these on a fresh save:

- launch with networking disabled;
- reach main menu, garage and first career event;
- complete normal races and return to career;
- save locally and reload after a Windows restart;
- progress from a fresh save through the complete main career;
- no mandatory real-money purchase, ad view, login, server response or timed energy gate;
- repeating the same race never reduces its normal repeatable payout;
- race premium currency reward remains `floor(repeatable credit payout × 0.50)`;
- all mandatory vehicles are obtainable before their first required event;
- vehicle purchase prices use the approved 20% baseline reduction unless an explicit progression override is documented;
- Premium and Sandbox saves remain separate if Sandbox ships in 1.0.

## Offline/service gates

- central connectivity state is forced offline;
- IGP/web/promo/store calls are local no-ops;
- cash-store product list is removed;
- Facebook/MSN initialization is disabled;
- WCPToolkit local storage/input/display functionality remains intact;
- no startup path waits indefinitely for a Gameloft endpoint;
- no gameplay progression requires a successful remote sync.

## Repack gates

- source AMS SHA-256 must be verified before transformation;
- AMS patch must reproduce the expected patched SHA-256;
- generated package uses ReXtreme identity and branding;
- original Store signature/blockmap metadata is discarded and regenerated;
- VC120 x86 dependency is bundled/installed automatically by Setup;
- package is signed with the ReXtreme signing chain;
- original Asphalt Xtreme and ReXtreme can coexist if desired.

## Installer gates

Visual requirements:
- user-provided ReXtreme logo replaces the previous text title;
- logo stays in the established title position;
- logo fades in smoothly;
- trailer is displayed vertically with a slight zoom/crop;
- trailer loops continuously;
- trailer starts muted;
- trailer fades in smoothly;
- buttons, status text and progress use eased transitions;
- installer has no visible PowerShell/console windows;
- RX executable icon is used for Setup, launcher and shortcuts.

Functional requirements:
- first run performs pre-flight checks before copying large files;
- install progress is based on real work, not fake timers;
- installation is resumable/recoverable after failure;
- repair verifies hashes and replaces only damaged files;
- uninstall preserves or explicitly offers to preserve saves;
- subsequent game launches do not rerun installer/bootstrap work.

## Performance targets

- installed launcher should reach game activation immediately, with no package rebuild;
- no downloads during ordinary launch;
- installer assets are local;
- expensive hash/package work is first-install/repair-only.

## Release process

1. Build 1.0 RC from clean 1.7.3.8 source.
2. Install on a clean Windows 10/11 test profile.
3. Complete offline smoke test.
4. Complete fresh-save economy/career test.
5. Verify repair/uninstall/save migration.
6. Freeze hashes.
7. Tag `v1.0.0` only after every mandatory gate above passes.

No alpha or RC is labeled 1.0 merely because it packages successfully.
