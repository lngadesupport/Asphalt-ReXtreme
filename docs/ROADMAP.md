# Asphalt ReXtreme Roadmap

## Phase 0 — Build identification
- Verify APPX manifest, package identity and executable entry point.
- Hash the original files used by the patcher.
- Inventory DLLs, assets, configuration files and runtime dependencies.

## Phase 1 — Offline boot
- Identify startup network dependencies.
- Separate optional telemetry/ads from services required for local gameplay.
- Make the title reach menus and local races without unavailable services.
- Preserve saves locally.

## Phase 2 — Offline preservation mode
- Implement an optional local-only economy profile.
- Make currency/upgrades non-blocking in preservation mode.
- Replace ad-gated local rewards with direct local actions where feasible.
- Unlock only content that is actually present in the user's installed build.

## Phase 3 — Modern PC settings
- FOV controls where camera systems permit.
- Configurable/unlocked frame rate with physics/timing verification.
- Resolution, aspect-ratio and ultrawide fixes.
- Windowed, borderless and fullscreen options.
- Input/controller improvements.

## Phase 4 — Multiplayer research
- Document the original protocol and server dependencies.
- Design a clean community backend if technically feasible.
- Keep community services independent from proprietary infrastructure.

## Safety / integrity
All patches should verify expected hashes before modifying files and should create backups. No proprietary game content should be committed to this repository.
