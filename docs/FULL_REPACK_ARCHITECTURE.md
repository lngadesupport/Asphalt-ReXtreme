# Portable Campaign Repack Architecture

## Decision

The signed APPX/MSIX repack approach is retired for the primary release.

Campaign Edition targets a **portable desktop/Win32-style runtime** that does not require Microsoft Store deployment or package identity.

See `CAMPAIGN_EDITION_ARCHITECTURE.md` for the normative runtime contract.

## Target layout

```text
Asphalt ReXtreme Campaign Edition/
├── AsphaltReXtreme.exe
├── GameData/
├── config/
├── save/
├── logs/
└── runtime/
```

The release builder transforms a supported legitimate 1.7.3.8 x86 source into this directory.

## Prohibited runtime dependencies

The final release must not require:
- APPX/MSIX installation or registration;
- AppUserModelID activation;
- Add-AppxPackage;
- App Installer;
- Microsoft Store license checks;
- Store IAP;
- Microsoft/Xbox sign-in;
- package certificates;
- Developer Mode or sideload policy.

Internet may remain enabled and the user may remain signed into Microsoft Store.

## Migration strategy

The original Store build uses package-family-dependent locations and UWP/platform helpers. Conversion therefore proceeds by:
1. inventorying package/Store/UWP references;
2. preserving essential local Windows functionality;
3. replacing package-path/save APIs with Campaign-owned local paths;
4. bypassing Store/IAP/auth activation paths;
5. replacing obsolete online/ad logic with local campaign behavior;
6. validating direct executable startup in a normal Windows session.

## Distribution

The public repository contains code, patch metadata and tooling only. Proprietary game files are transformed locally from a legitimate source copy.
