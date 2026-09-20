# Asphalt ReXtreme

Fan-made preservation and modernization project for the Windows build of **Asphalt Xtreme**.

## Primary release: Campaign Edition

The current target is **Asphalt ReXtreme: Campaign Edition**: a portable,
paid-game-style offline edition that behaves like a normal Windows racing game.

Core requirements:
- launch from `AsphaltReXtreme.exe` without Microsoft Store or APPX/MSIX registration;
- no Microsoft/Xbox authentication requirement;
- internet may remain enabled and the user may stay signed into Microsoft Store;
- campaign/career, races, garage, shop and local progression work without old services;
- no ad-gated progression;
- no real-money IAP dependency;
- race rewards grant credits and premium currency;
- shop content (cars, paint, upgrades, parts, etc.) costs **20% of original price**;
- repeated-race rewards remain at 100% for the first 10 runs and never fall below 98%;
- local portable saves with recoverable writes;
- preserve original game visuals unless a technical compatibility fix is required.

See `docs/CAMPAIGN_EDITION_ARCHITECTURE.md`.

## Current target build

- Package source: `A278AB0D.AsphaltXtreme`
- Version: `1.7.3.8`
- Architecture: x86
- Original platform: Windows / Microsoft Store APPX
- Campaign target: portable desktop/Win32 runtime

## Development tooling

`tools/store_dependency_audit.py` scans an extracted source build for Microsoft
Store/UWP/package identity, Microsoft/Xbox authentication and legacy Gameloft
service coupling. It is read-only.

Example:

```powershell
python tools/store_dependency_audit.py "C:\Games\Asphalt Xtreme" ^
  --json reports\store-audit.json ^
  --markdown reports\store-audit.md
```

The existing build, economy, XTEA and patching tools remain part of the reverse
engineering workflow.

## Distribution model

The public repository contains project code, documentation, patch metadata and
tools only. Original executables, APPX packages, DLLs, game assets and other
proprietary content are not committed here.

The intended release builder transforms a legitimate user-provided 1.7.3.8 x86
source locally into the Campaign Edition.

## Planned portable layout

```text
Asphalt ReXtreme Campaign Edition/
├── AsphaltReXtreme.exe
├── GameData/
├── config/
├── save/
├── logs/
└── runtime/
```

## Status

Reverse-engineering and Campaign Edition conversion work in progress.
