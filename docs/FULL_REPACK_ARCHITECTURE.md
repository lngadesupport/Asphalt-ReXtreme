# Full Repack Architecture

## Decision

For the primary Windows Offline Edition, ReXtreme will move toward a **full repack** of the compatible Asphalt Xtreme 1.7.3.8 x86 source rather than trying to preserve the original Microsoft Store package identity.

The user-facing target becomes:

```
Asphalt ReXtreme/
├── AsphaltReXtreme.exe
├── ReXtreme.appx / installation cache
├── ReXtreme/
└── original game payload transformed into the ReXtreme build
```

## Why

A full repack gives ReXtreme control over:
- package identity;
- publisher/signing identity;
- manifest;
- versioning;
- dependencies;
- app capabilities;
- package metadata;
- all modified binaries/data;
- startup/launcher behavior;
- future migration of saves.

It avoids relying on the original Store signature or Store-managed deployment state.

## New identity

The final ReXtreme package should use a distinct package identity, e.g.:

- Name: `ReXtreme.AsphaltXtreme`
- DisplayName: `Asphalt ReXtreme`
- Publisher: ReXtreme-controlled signing subject
- Version: independent ReXtreme versioning

The original Store package can remain installed separately because the package family will be different.

## Installation model

The full game payload may remain approximately 1.5 GB. The launcher/installer should:
1. verify a supported legitimate 1.7.3.8 x86 source;
2. transform it into the ReXtreme build;
3. install the ReXtreme signing certificate when required;
4. install the VC120 x86 framework dependency;
5. install the signed ReXtreme APPX/MSIX;
6. launch the ReXtreme AppUserModelID.

Windows 10 2004+ generally supports sideloading signed non-Store MSIX/AppX packages without enabling Developer Mode, provided the signing certificate is trusted.

## Consequences

Changing package identity changes package-family-dependent locations such as LocalState. ReXtreme must therefore:
- migrate/import old saves deliberately;
- use a ReXtreme-owned local save model;
- audit any hard-coded original package-family references;
- patch Store/IAP/social/service assumptions that depend on the old identity.

## Distribution

Public releases should not redistribute original proprietary game content. The public installer/rebuilder should transform a legitimate user-provided source package into the ReXtreme package locally.

Private development/test builds may contain transformed game files when supplied by the project owner for testing.
