# ReXtreme game — Presentation / Replay / Photo runtime

This document describes implemented code, not aspirational UI.

## Architectural boundary

The original Asphalt Xtreme race physics, AI, renderer, controls, animation,
audio and race presentation remain preserved. ReXtreme does not introduce a
second vehicle physics system.

Presentation features are exposed through the Campaign Core gateway selector:

- selector: `0xC0DECA90`
- entry: `CampaignPresentationInvoke`

No camera/renderer address is guessed. A runtime adapter may apply a setting
only after its original 1.7.3.8 path is verified.

## Graphics and camera settings

`CampaignPresentationOptions.dat` is a verified allowlist.

Missing/empty allowlist is valid and means:

> expose no additional renderer/camera settings.

A capability entry is rejected unless it carries the VERIFIED flag. The source
builder also requires explicit evidence before it can generate such an entry.

Current verified capability count in repository source: **0**.

Consequently FOV, camera distance, camera height and camera smoothing remain at
the original Asphalt Xtreme behavior by default. Non-zero overrides are rejected
until their respective capability is verified.

Generic verified values are persisted under `[VerifiedPresentation]` in
`ReXtreme.ini`.

Audit tools:

- `AUDIT-PRESENTATION-CAPABILITIES.cmd`
- `AUDIT-ORIGINAL-SETTINGS-UI.cmd`

The first finds candidate renderer/camera/replay references. The second finds
candidate original UI assets/components. Neither tool promotes candidates to
verified bindings automatically.

## Replay runtime

Implemented independently of race simulation:

- dynamic sample ring buffer;
- start / stop / clear / record;
- race metadata (event, track, player car, mode, session id);
- chronological sample access;
- timeline markers:
  - start;
  - takedown;
  - jump;
  - wreck;
  - overtake;
  - finish;
  - custom;
- save/load `.rexreplay`;
- replay file version 3;
- atomic save through temporary file;
- integrity hashes for samples and markers;
- corrupted/truncated replay rejection;
- playback state;
- play / pause;
- seek;
- playback speeds:
  - 0.10x;
  - 0.25x;
  - 0.50x;
  - 1.0x;
  - 2.0x;
  - 4.0x;
- advance by real-time delta;
- forward/back sample step;
- nearest sample lookup by timeline time/entity;
- previous/next marker lookup.

### Not yet claimed as integrated

The race-engine transform sampling hook and camera playback adapter are not yet
mapped to verified original addresses. Therefore the runtime above is ready for
the adapters, but Replay is not yet presented as a finished in-game feature.

## Photo Mode runtime

Implemented state:

- inactive/active;
- original/free/orbit camera mode;
- hide HUD state;
- target vehicle/entity;
- FOV state;
- distance / height;
- free-camera position XYZ;
- pitch / yaw / roll;
- camera movement speed.

### Not yet claimed as integrated

Entering Photo Mode from the original pause UI and applying free-camera values
to the preserved Asphalt Xtreme camera still require verified original UI/camera
bindings.

## Portable data

Campaign gameplay state now prefers:

`UserData/CampaignEdition/CampaignSave.dat`

The rebuilder prepares:

- `UserData/CampaignEdition/`
- `UserData/Replays/`
- `UserData/Screenshots/`

When PortableSave is enabled, an existing Campaign save from the historical
Microsoft Store LocalState path is copied into portable storage if no portable
save exists. The original file is left untouched.

If portable storage cannot be created, Campaign Core falls back to the legacy
LocalState path instead of losing the save.

## Diagnostics

Campaign command `CAMPAIGN_OP_DIAGNOSTICS` reports:

- portable-save mode;
- Campaign save version;
- pending race-session presence.

Presentation diagnostics report:

- settings revision;
- verified capability count;
- replay recording/sample/marker state;
- playback loaded/playing/time state;
- Photo Mode active/camera mode.

The backend-free Profile summary command exposes existing local Campaign data
for future original-UI adapters without consulting Gameloft services.

## Validation

The CI builds the x86 Campaign Core with no CRT dependency and runs a native
presentation smoke test. The smoke test exercises settings, verified capability
gating, Replay save/load/integrity/timeline behavior and Photo Mode state.

Python tests validate:

- Campaign rebuilder;
- portable UserData layout;
- binary presentation audit;
- original UI audit;
- verified capability catalog builder.

## Next verified-integration work

1. Run the presentation audits against the exact supported Asphalt Xtreme
   1.7.3.8 source tree.
2. Verify the original Settings UI component bindings.
3. Verify the original camera getter/setter/update path.
4. Add only proven capabilities to the allowlist.
5. Bind the original UI to the generic capability API.
6. Map a safe per-frame race transform source for Replay recording.
7. Map pause-state/camera bindings for Photo Mode.
8. Keep all race physics/AI/control behavior untouched.
