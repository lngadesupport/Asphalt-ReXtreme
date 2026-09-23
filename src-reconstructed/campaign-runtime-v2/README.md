# Campaign Runtime V2

This is the clean-room replacement for the original online CraftCar/event/profile path.

## Authority boundary

The original garage UI is retained only as a visual/input surface.

The following original systems are **not authoritative and must not be called by the V2 craft path**:

- `prokitsv2::CraftCarRequestImpl`
- `CraftCar_Caller`
- original request/result JSON handlers
- original event synchronizer
- original CraftCar listener/observer completion path
- original backend inventory mutation
- original backend ownership mutation
- IGP runtime/bootstrap logic
- server-side persistence assumptions

Campaign Runtime V2 owns:

- car ownership
- blueprint inventory
- craft validation
- atomic craft transaction
- state revision
- local persistence
- local event history
- garage action routing

## Persistence format

The V2 save is intentionally independent:

```text
REXTREME_CAMPAIGN_V2
version=1
revision=12
owned=1001
owned=1007
bp=2401:18
bp=2402:7
```

The first integration target is:

```text
GarageBottomBar MONTAR
        |
        v
Campaign V2 GarageActionRouter
        |
        +--> selected car id
        +--> Campaign recipe
        +--> local atomic transaction
        +--> save
        +--> UI refresh only
```

## Binary integration rule

Only UI-facing adapters may call original rendering/selection functions. They may not call original CraftCar/backend/profile/inventory completion logic.

The first known stable selection bridge remains:

- `GS_Garage + 0x2D4` selected-car holder
- selected-car id helper `0x00D805F0`

Those are treated as UI-selection adapters, not business logic.

No guessed ownership predicate should be patched. Ownership gates must be redirected only after their call sites are proven.
