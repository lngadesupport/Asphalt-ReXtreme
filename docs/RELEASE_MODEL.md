# Release model

## Asphalt ReXtreme: Campaign Edition

Campaign Edition is the primary release target.

### User experience

The intended flow is:

1. Obtain/own a compatible original Asphalt Xtreme Windows 1.7.3.8 x86 build.
2. Run the ReXtreme importer/rebuilder once.
3. The rebuilder verifies the source and creates a portable Campaign directory.
4. Launch `AsphaltReXtreme.exe` directly from that directory.

Normal play must not require:
- Microsoft Store;
- APPX/MSIX registration;
- Microsoft/Xbox authentication;
- Store licensing or IAP;
- Gameloft services;
- ad servers;
- an active community backend;
- Python/developer tools;
- manual package policy changes.

Internet may remain enabled and the Windows user may remain signed into
Microsoft Store.

### Campaign profile

Campaign Edition uses:
- local saves;
- campaign/career progression;
- credits and premium currency earned by racing;
- no advertisement gates;
- no real-money progression;
- shop content at 20% of original price by default;
- repeat-race reward floor of 98% after the 10th completion;
- no monetization energy/timer blocks.

### Sandbox profile

An optional Sandbox profile may provide unrestricted progression for testing or
free play. It uses a separate save and is not the default balance.

## Repository vs release package

GitHub stores project-owned code, patch descriptions, analysis tools and
documentation only.

Original proprietary game assets and binaries are not published in the
repository. The rebuilder transforms a legitimate user-provided source locally.

## Online/community work

Any future community multiplayer/backend work is a separate release track and
must never become a dependency of Campaign Edition.
