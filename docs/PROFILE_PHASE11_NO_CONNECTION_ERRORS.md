# Phase 11 — No Connection Errors

Phase 11 removes the Campaign Edition's dependency on connectivity-error UI.

Static analysis of the pristine 1.7.3.8 x86 AMS found **15 complete construction sites** that use both:

- `STR_POPUP_NO_INTERNET_DESCRIPTION`
- `STR_POPUP_NO_INTERNET_TITLE`

## Classification

12 / 15 are directly gated by the global connectivity getter at VA `0x00FAD9D0` (file offset `0x00BACDD0`).

The pristine implementation returns byte `[ecx+0x4B0]`.
The old Campaign Phase 5 patch forced this value to false, which caused local Campaign operations to enter the game's "no internet" branches.

Phase 11 changes that compatibility shim to logical **true**.

This does not restore obsolete remote services:
- profile sync remains bypassed locally;
- Microsoft Store purchase remains blocked;
- Vungle remains disabled.

The remaining 3 / 15 popup paths are remote-result callbacks. Their explicit network-failure branches are redirected to each callback's pre-existing success/local-completion path:

- file offset `0x004FBCF0`
- file offset `0x004FD6A5`
- file offset `0x0064A789`

## Scope

The goal is that Campaign Edition never shows the generic **NO_INTERNET / FALHA DE CONEXÃO** popup during:

- startup / age-gender consent;
- race result handling;
- upgrades;
- box operations;
- purchases;
- inventory/profile updates;
- other local gameplay flows.

Other gameplay errors that are not connectivity errors remain intact.

## Rollback

Run `RESTORE-PROFILE-PHASE11.cmd`.
