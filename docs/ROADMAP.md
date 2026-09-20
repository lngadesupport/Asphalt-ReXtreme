# Asphalt ReXtreme Roadmap

## Release track A — Offline Edition 1.0

### Phase 0 — Build identification — complete
- [x] Verify target package: Asphalt Xtreme 1.7.3.8 x86.
- [x] Verify AMS.exe and critical DLL SHA-256 values.
- [x] Inventory package files, services, runtimes and save assumptions.
- [x] Identify VC120 x86 framework dependency.
- [x] Reverse-engineer xml.bin / XTEA stream handling sufficiently for deterministic data transforms.

### Phase 1 — Offline core — RC implementation
- [x] Force central connectivity state offline.
- [x] Neutralize IGP/promo/store initialization through verified local transforms.
- [x] Remove cash-store product listing from deterministic data transforms.
- [x] Disable Facebook/MSN initialization in the offline data profile.
- [x] Preserve WCPToolkit local storage/input/display functionality.
- [ ] Pass real Windows boot smoke test with networking disabled.
- [ ] Verify menu → garage → race → results → career loop on RC1.
- [ ] Verify local save persistence after Windows restart.

### Phase 2 — Premium offline economy — RC implementation
- [x] Baseline vehicle credit price multiplier: 0.80.
- [x] Race Premium reward hook: floor(repeatable credit payout × 0.50).
- [x] Remove energy/fuel/maintenance/fuse monetization gates from approved data transforms.
- [x] Disable repeat-race diminishing/cap/cooldown policy in the ReXtreme profile.
- [x] Audit all 300 main-career events and mandatory car gates.
- [ ] Resolve every hardcurrency-only mandatory-car gate in the final balance.
- [ ] Verify upgrade affordability through a complete fresh-save career simulation.
- [ ] Complete a fresh-save career validation on the real RC build.

### Phase 3 — Independent Full Repack — RC implementation
- [x] Replace original Store identity with ReXtreme.AsphaltXtreme.
- [x] Set independent ReXtreme publisher/version metadata.
- [x] Discard original signature/blockmap metadata before repacking.
- [x] Apply only hash-verified binary patches.
- [x] Add manifest transform regression tests.
- [x] Add private payload assembler with SHA-256 integrity manifest.
- [x] Add signed APPX + VC120 build pipeline.
- [ ] Build the complete ~1.8 GiB private RC1 from the full user-provided source on Windows.
- [ ] Install the signed RC1 on a clean Windows profile.
- [ ] Verify original Asphalt Xtreme and ReXtreme can coexist.

### Phase 4 — Installer / launcher — RC implementation
- [x] Self-contained x64 WPF installer shell.
- [x] Official ReXtreme logo in the approved title position.
- [x] Logo and trailer eased fade-in animations.
- [x] Vertical trailer panel, slight zoom, continuous loop and muted startup.
- [x] Real Windows package deployment progress.
- [x] JOGAR AGORA detection for an existing install.
- [x] REPARAR deployment path.
- [x] Mandatory APPX/certificate/dependency SHA-256 verification.
- [x] No visible PowerShell window in the installer deployment engine.
- [ ] Integrate the final private vertical trailer render.
- [ ] Embed the approved RX executable icon in final Setup/launcher binaries.
- [ ] Produce the final one-download Setup wrapper around shell + private payload.
- [ ] Verify uninstall/save-preservation behavior.

### Phase 5 — Modern PC settings
These do not block the first RC boot, but any feature advertised for 1.0 must be verified before release:
- [ ] FOV control.
- [ ] Configurable/unlocked frame rate with physics/timing verification.
- [ ] Modern resolution/aspect-ratio and ultrawide behavior.
- [ ] Borderless/windowed/fullscreen behavior.
- [ ] Controller/input improvements.
- [ ] Stable user-facing ReXtreme.ini integration.

### Phase 6 — 1.0 release gate
v1.0.0 is created only after:
- [ ] clean-machine install succeeds;
- [ ] first boot succeeds with networking disabled;
- [ ] fresh save is created and reloads correctly;
- [ ] career is completable without server, login, ads or purchases;
- [ ] mandatory cars/upgrades remain affordable;
- [ ] repeated races retain full rewards;
- [ ] repair succeeds without deleting saves;
- [ ] restart/save persistence succeeds;
- [ ] installer/launcher assets and branding are final;
- [ ] release hashes are frozen.

## Release track B — Online Edition (later)

Only after Offline Edition 1.0 is stable:
- document remaining original protocol/server dependencies;
- design any community backend as a separate edition;
- keep Offline Edition completely independent from community infrastructure.

## Distribution integrity

The public repository contains project-owned code, documentation and patch metadata only. Original proprietary binaries/assets are transformed locally from a legitimate user-provided source and are not committed to the public repository.
