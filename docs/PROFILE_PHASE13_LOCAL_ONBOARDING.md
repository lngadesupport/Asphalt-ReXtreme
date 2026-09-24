# Phase 13 — Local onboarding handler

Phase 13 replaces the two broad Phase 12 body-skips inside the age/gender onboarding function with targeted control-flow patches at the function's own connectivity decisions.

## Verified anchors

- Phase 5 AMS SHA-256: `56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3`
- Handler start: `0x006A1CA0`
- Gate 1: `0x006A1CE1`, original `JNZ 0x006A1DE5`
- Gate 2: `0x006A1E03`, original `JNZ 0x006A1EE1`
- Former Phase 12 body-skip sites `0x006A1CE7` and `0x006A1E09` are not used by Phase 13.

## Model

Global connectivity stays false/offline, exactly as in Phase 5.

Only the two connectivity checks inside the age/gender handler are changed to unconditional jumps to the existing success continuations:

- `0x006A1CE1: 0F 85 FE 00 00 00 -> E9 FF 00 00 00 90`
- `0x006A1E03: 0F 85 D8 00 00 00 -> E9 D9 00 00 00 90`

This avoids enabling obsolete backend behavior globally while allowing the native first-run handler to initialize and complete its local path.

All other Phase 12 network-error coverage remains, along with the Phase 9 native-profile changes and Phase 10 profile-loading neutralizations.

## Build

Run:

`GET-PHASE13.cmd`

then:

`BUILD-PROFILE-PHASE13-LOCAL-ONBOARDING.cmd`

Launch with:

`_PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd`

## First runtime acceptance test

1. Reach age/gender onboarding.
2. Select age 21.
3. Press **ACEITAR**.

Expected behavior: no network-error popup or remote wait; the handler completes and startup advances.

If the build needs to be reverted, run `RESTORE-PROFILE-PHASE13.cmd`, which restores the hash-verified Phase 5 AMS backup.
