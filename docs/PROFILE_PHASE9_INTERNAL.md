# Phase 9 — Internal Campaign Profile

Phase 8 bootstrap/seeding is deprecated. Testing confirmed that this build does not create `LocalState\localprofile` or `profile` before the legacy online profile synchronization succeeds.

Phase 9 therefore uses the game's own in-memory default profile object.

## Verified constructor behavior

The profile initializer beginning near file offset `0x0069B7A0`:

1. constructs/parses the local profile source object;
2. evaluates its local validity and stores a result at object offset `+0x30`;
3. allocates a `0x6D0`-byte profile object;
4. invokes the game's profile constructor;
5. stores the resulting object at `+0x3C`.

The allocation/construction occurs even when no usable `localprofile` file exists.

## Phase 9 native patches

- `0x0069B8C6`: route first local validation failure through the valid result.
- `0x0069B8E6`: return true for the secondary local validation failure path.
- `0x0092B82A`: bypass the dead remote startup-profile sync block and advance the startup state machine.

No fabricated profile binary is embedded and no Store entitlement is simulated.

## UI

Where the Portuguese text is stored plainly in the package resources, the build performs an exact-length internal replacement:

`VERIFICANDO PERFIL ON-LINE`
→
`CARREGANDO PERFIL LOCAL...`

Further localization work should target the exact localization container after startup functionality is confirmed.

## Persistence

The profile object is native to the game. Phase 9 relies on the game's normal save path after startup. If persistence still requires an additional state flag, that flag will be patched in the native save path rather than by inventing a profile file format.
