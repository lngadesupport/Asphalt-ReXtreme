# Profile Fallback Phase 7

## Goal

Replace the dead legacy online-profile startup loop with an explicit offline fallback while preserving the original profile/save pipeline.

Desired user flow:

1. Game starts.
2. A small status indicator shows `Carregando perfil...`.
3. Legacy online profile verification is not allowed to block indefinitely.
4. The existing login/network error popup is shown immediately after the online attempt is considered unavailable.
5. The existing **Retry / Tentar novamente** action is repurposed as the offline fallback trigger:
   - if `LocalState\localprofile` and `LocalState\profile` exist, load them through the game's own local-profile path;
   - if they do not exist, invoke the game's own local-profile creation/initialization path and then load it;
   - only after the local profile is accepted should startup continue.
6. If local loading fails, keep the error popup visible and report a local-profile error instead of looping on the dead backend.

## Why this replaces the previous skip patches

Phase 6 tests proved that suppressing the login-error handler or skipping one `STR_MENU_SYNC_LOADING` branch does not advance startup. The UI is a symptom; an internal profile/sync state remains pending.

The client already creates local profile data:
- `LocalState\localprofile`
- `LocalState\profile`
- `LocalState\settings`

Therefore Phase 7 should transition the profile state machine rather than hide loading UI.

## Known binary anchors (build 1.7.3.8 x86)

Verified Campaign Phase 5 AMS SHA-256:

`56e9dbde7f7f3a75b3542a691fb45ad5bf46b86e87cb9fa11854ec1862e62ae3`

### Sync/loading strings

`STR_MENU_SYNC_LOADING` xrefs:
- file offset `0x00685FD0`
- file offset `0x006CF9E6`
- file offset `0x0092B8BB`

The first two are UI/loading constructors. The third sits in a larger startup/profile state machine and is the preferred state-machine anchor.

### Login-error popup

`STR_POPUP_LOGIN_ERROR_DESCRIPTION` / `TITLE` appear in four routines:
- `0x006A4E50`
- `0x007405F0`
- `0x007408A0`
- `0x007409F0`

The `0x00740xxx` family contains repeated UI action/virtual-call patterns and is the primary candidate set for the Retry callback path.

### Local-profile initialization

The local-profile construction path around file offsets `0x0069B8BF-0x0069BAxx`:
- builds/validates local-profile objects;
- stores a boolean result at object offset `+0x30`;
- constructs a secondary object at `+0x3C`.

The earlier test that forced only `+0x30` was insufficient, so Phase 7 must follow the complete local-profile state transition.

## Implementation plan

### 7A — Status indicator

Prototype as a small companion overlay attached to the Asphalt Xtreme window. This keeps visual changes independent from the game's XBF resources. Once the profile fallback is stable, the indicator can be integrated into the packaged UI if desired.

States:
- `Carregando perfil...`
- `Perfil online indisponível`
- `Carregando perfil local...`
- `Criando perfil local...`
- `Perfil local carregado`
- `Falha ao carregar perfil local`

### 7B — Fail fast into existing popup

Do not merely suppress `STR_MENU_SYNC_LOADING`. Transition the startup profile state from remote-pending to remote-unavailable and invoke the existing login-error popup path.

### 7C — Retry -> local profile

Hook the confirmed Retry action in the `0x00740xxx` popup family. The Retry action should call the complete local-profile loader/initializer, not just set the `+0x30` flag.

### 7D — Create only when missing

Never fabricate a profile binary format. If local files are absent, call the game's own creation/initialization routine. This preserves serialization, checksums and future save compatibility.

### 7E — Resume startup

After local load succeeds, transition the same state machine used by a successful profile initialization so the normal menu/tutorial flow continues.

## Safety / rollback

All Phase 7 binary work must:
- hash-guard the exact Phase 5 AMS;
- create a pristine Phase 5 backup;
- use a separate test copy or reversible byte patches;
- never modify Store licensing or entitlement simulation;
- preserve `LocalState` profile files unless the user explicitly requests a reset.
