# Phase 8 — Embedded Campaign Profile

Phase 8 replaces the experimental external/profile-skip approach with an embedded Campaign profile model.

## Runtime model

The package tree contains:

```
CampaignProfile/
  seed/
    localprofile
    profile
    settings        # when available
  user/
    localprofile
    profile
    settings
  campaign-profile-manifest.json
```

`seed` is the immutable profile bundled with Campaign Edition.
`user` is the persistent mirror of the player's evolving profile.

UWP still requires writable data to live under `LocalState` while the process runs. Therefore the Campaign runtime silently restores `user` (or `seed` on first use) into LocalState before launch, then mirrors the resulting profile back into the game tree when AMS exits.

This makes the profile survive package unregistration/re-registration while avoiding any user-visible profile creation flow.

## Native UI text

The builder performs a conservative same-size byte replacement when the Portuguese loading text exists plainly in the package resources:

`VERIFICANDO PERFIL ON-LINE`
→
`CARREGANDO PERFIL LOCAL...`

It also inventories the locations of:
- `STR_MENU_SYNC_LOADING`
- `STR_POPUP_LOGIN_ERROR_DESCRIPTION`
- `STR_POPUP_LOGIN_ERROR_TITLE`

The key inventory is used for the next internal UI patch once the exact localization container is confirmed.

## Rules

- Do not write mutable saves directly into immutable package resources.
- Do not fabricate Store licensing or entitlements.
- Always restore the verified Phase 5 AMS before building Phase 8.
- The embedded seed is never overwritten after first capture.
- The user mirror is updated after every successful game session.
