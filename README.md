# Asphalt ReXtreme

Fan-made preservation and modernization project for the Windows build of **Asphalt Xtreme**.

## Goals

- Preserve the original Windows PC build and keep the campaign playable offline.
- Remove dependencies on discontinued online services where they are not required for local gameplay.
- Provide a local/offline economy mode for preservation and testing.
- Add modern PC options such as configurable FOV, frame-rate limit/unlock, modern resolutions, borderless/windowed modes and controller improvements.
- Research a community multiplayer replacement separately after the offline client is stable.

## Current target build

- Package: `A278AB0D.AsphaltXtreme`
- Version: `1.7.3.8`
- Architecture: `x86`
- Platform: Windows / Microsoft Store APPX

## Repository policy

This repository is intended to contain only original project code, documentation, patch metadata and tools.

**Do not commit original game executables, assets, APPX packages, DLLs, archives, keys, signatures or other proprietary Gameloft/Netflix content.**

Users must provide their own legitimate copy of the game files when a future patcher requires them.

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

Early reverse-engineering / preservation research. No public binary patch is ready yet.
