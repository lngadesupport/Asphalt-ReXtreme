# Asphalt ReXtreme

Fan-made preservation and modernization project for the Windows build of **Asphalt Xtreme**.

## Primary release: Offline Edition

The first release target is a **plug-and-play offline edition** focused on preservation and reliability.

Goals:
- Launch directly into a usable offline game flow with no dead service dependency.
- Keep campaign/career, races, garage and local progression available.
- Provide an optional preservation economy with unlimited local currency and no upgrade grind.
- Remove local content gates that only exist because ads or discontinued services are unavailable.
- Store progress locally.
- Add modern PC options such as configurable FOV, frame-rate limit/unlock, modern resolutions, borderless/windowed modes and controller improvements.
- Avoid requiring users to run development tools, edit files manually, configure servers or install Python.

The later online/community edition is a **separate project phase** and will not be required for the Offline Edition.


## Master Collector

For development and reverse-engineering data collection, use **`REXTREME_COLETOR_MASTER.bat`**.

This is the project's definitive one-click collector and supersedes the earlier staged analysis scripts. It generates a timestamped ZIP containing build hashes, file inventory, PE metadata, key binaries/configuration candidates, economy/network/graphics strings, URL/domain findings, AppX information and save-state metadata.

Two modes are available:

- **Complete Safe** — default; does not copy save/profile contents.
- **Deep** — also snapshots package save/profile files when save-format analysis is required.

The collector is read-only with respect to the game directory and can be reused throughout the entire Offline Edition development cycle.

## Current target build

- Package: `A278AB0D.AsphaltXtreme`
- Version: `1.7.3.8`
- Architecture: `x86`
- Platform: Windows / Microsoft Store APPX

## Distribution model

The public repository contains original project code, documentation, patch metadata and tools only.

Original executables, APPX packages, DLLs, game assets and other proprietary content are not committed here. A release builder/patcher will verify and transform a legitimate local copy into the ReXtreme Offline Edition.

The end-user goal is a one-click result:

```
Asphalt ReXtreme Offline/
├── AsphaltReXtreme.exe
├── ReXtreme.ini
└── GameData/
```

After the user's legitimate game files have been imported once, normal play should require only launching `AsphaltReXtreme.exe`.

## Planned structure

```
Asphalt-ReXtreme/
├── config/
├── docs/
├── launcher/
├── patches/
├── tools/
└── tests/
```

## Status

Early reverse-engineering / preservation research against build `1.7.3.8 x86`.
