# Phase 12 — Local Offline / No Network UI

Phase 11 proved that globally reporting connectivity as available can let obsolete remote code wait indefinitely.

Phase 12 deliberately keeps Campaign Edition logically offline and removes the network-error UI itself.

## Design

- global connectivity remains false/offline;
- profile sync loading sites remain neutralized;
- all 15 known complete NO_INTERNET popup blocks are bypassed;
- each popup block jumps to its existing local cleanup/return path;
- no remote backend is enabled.

This covers the 15 static construction sites that reference both:

- `STR_POPUP_NO_INTERNET_DESCRIPTION`
- `STR_POPUP_NO_INTERNET_TITLE`

Three are result callbacks and twelve are connectivity-gated code paths.

## Why this replaces Phase 11

Phase 11 changed the global connectivity getter to true. That removed the popup but could allow a dead remote request to begin, producing a freeze.

Phase 12 does not do that.

## Rollback

Run `RESTORE-PROFILE-PHASE12.cmd`.
