# Current project status — 2026-09-21

## Current runtime state

The current tested build is **Phase 12 — Local Offline / No Network UI**.

Observed behavior on Windows:

1. Game launches successfully as the registered loose UWP package.
2. Initial online-profile verification no longer blocks startup.
3. Generic `NO_INTERNET / FALHA DE CONEXÃO` UI no longer appears in the current Phase 12 path.
4. The game reaches the first-run age/gender screen.
5. Current blocker: pressing **ACEITAR** on the age/gender screen does nothing; the screen remains active and startup does not continue.

## Next technical direction

Do not return to Phase 8 or fabricate a `localprofile` binary.

The preferred next step is to identify and preset the native first-run/profile fields so Campaign Edition starts with onboarding already completed. Candidate state includes:

- age preset (currently user tested with age 21);
- gender preset;
- privacy/terms/EULA accepted;
- first-run false;
- profile initialized;
- onboarding completed.

The preferred solution is internal state initialization, not merely hiding the age/gender UI.

## Important working phases

- Phase 9: native default profile object + startup profile gate bypass.
- Phase 10: neutralizes the three known `STR_MENU_SYNC_LOADING` sites.
- Phase 11: deprecated; global logical online=true caused remote waits/freezes.
- Phase 12: current base. Keeps connectivity logically offline and bypasses 15 known complete NO_INTERNET popup blocks.

## Current baseline

Working folder expected on user machine:

`CAsphalt-ReXtreme-Baseline\_PACKAGE_PHASE5`

Expected Phase 5 AMS SHA-256:

`56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3`

Repository branch:

`campaign-edition-win32`

Repository:

`lngadesupport/Asphalt-ReXtreme`

## Rule

The final Campaign Edition should not depend on remote profile sync, Microsoft Store purchase, Vungle ads, or generic network-error UI for local gameplay.
