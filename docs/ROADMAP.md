# Asphalt ReXtreme Roadmap

## Release track A — Offline Edition

### Phase 0 — Build identification
- Verify APPX manifest, package identity and executable entry point.
- Hash the original files used by the patcher.
- Inventory DLLs, assets, configuration files and runtime dependencies.
- Identify save/profile locations and package-runtime assumptions.

### Phase 1 — Offline boot
- Identify startup network dependencies.
- Separate optional telemetry/ads from services required for local gameplay.
- Remove hangs/errors caused by unavailable endpoints.
- Make the title reach menus, garage and local races with networking unavailable.
- Preserve saves locally.

### Phase 2 — Offline preservation economy
- Implement an optional local-only preservation profile.
- Unlimited local currencies/resources where technically feasible.
- Upgrades without grind/cost in preservation mode.
- Convert ad-gated local rewards/actions into direct offline actions.
- Remove timers/online gates that have no meaningful offline function.
- Unlock only content actually present in the user's installed build.
- Keep irreversible changes behind backups/versioned saves.

### Phase 3 — Plug-and-play packaging
- Build a one-click importer/patcher for a legitimate original installation.
- Verify exact source hashes before patching.
- Copy required files into an independent ReXtreme directory.
- Apply patches without requiring manual hex editing.
- Bundle project-owned runtime/configuration files.
- Create a launcher/entry point with sensible defaults.
- No server setup, Python, developer mode or command-line steps required for normal play.
- Add repair/restore/update paths.

### Phase 4 — Modern PC settings
- FOV controls where camera systems permit.
- Configurable/unlocked frame rate with physics/timing verification.
- Resolution, aspect-ratio and ultrawide fixes.
- Windowed, borderless and fullscreen options.
- Input/controller improvements.
- User-editable `ReXtreme.ini` plus launcher UI where useful.

### Phase 5 — Offline release hardening
- Test clean Windows installations.
- Test first launch with networking disabled.
- Verify career progression and save persistence.
- Verify cars/upgrades/events available in the target build.
- Validate 60/120/144+ FPS behavior and race timing.
- Crash logging and safe fallback configuration.
- Produce reproducible release builds.

## Release track B — Online Edition (later)

Only after the Offline Edition is stable:
- Document the original protocol and server dependencies.
- Design a clean community backend if technically feasible.
- Keep community services independent from proprietary infrastructure.
- Maintain compatibility as a separate edition/profile so offline play never depends on the community backend.

## Integrity

All patches must verify expected hashes before modifying files and create backups. No proprietary game content is committed to this repository.
