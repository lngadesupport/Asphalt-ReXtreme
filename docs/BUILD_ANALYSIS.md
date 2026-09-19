# Build analysis

The first analysis target is the extracted Windows package for:

- `A278AB0D.AsphaltXtreme`
- version `1.7.3.8`
- architecture `x86`

## Local inventory

Run:

```powershell
py tools/analyze_build.py "D:\Games\Asphalt Xtreme Extracted"
```

The tool writes:

- `analysis-output/build-report.json`
- `analysis-output/summary.txt`

These reports contain hashes, package identity, discovered URLs/domains and selected strings related to online services, ads, economy, graphics and input.

The tool is read-only. It does not patch or launch the game.

## What we inspect first

1. `AppxManifest.xml`
2. main executable (historically `AMS.exe`)
3. game DLLs
4. local configuration/save files
5. obsolete service endpoints and advertisement SDK references
6. economy / upgrade / entitlement checks
7. frame-rate, resolution, aspect ratio and camera/FOV code paths

Binary patches must only be added after exact hashes and offsets are verified against this build.
