# R17 Local Event Runtime

R17 replaces the dead online event/craft synchronization path with a local subsystem owned by Campaign Edition.

## Architecture

\`\`\`text
original GarageBottomBar MONTAR signal
                 |
                 v
GS_Garage::BuildCar entry (0x00A87960)
                 |
                 | runtime JMP installed by IGPLib_x86.dll
                 v
          LocalEventRuntime
                 |
          CraftRequested(car_id)
        /        |        |        \
       v         v        v         v
 Inventory   Profile   Garage   Persistence
 Consumer   Consumer  Consumer   Consumer
       \         |        |         /
                 v
          LocalEventStore
                 |
                 v
 %LOCALAPPDATA%\ReXtremeLocal\campaign.ini
                 |
                 v
          LocalGarageUI
\`\`\`

The original CraftCar request/result dispatcher, original event synchronizer, and the R16 fake callback are not used after R17 installs its hook.

## Runtime integration

R17 is hosted by \`IGPLib_x86.dll\`, which the game already loads. The existing IGP exports remain stubbed as before.

The runtime resolves the selected car using the same helper used by the original BuildCar path:

- \`GS_Garage::BuildCar = 0x00A87960\`
- \`GS_Garage + 0x2D4\` selected-car holder
- selected-car id helper \`0x00D805F0\`

No persistent byte patch is made to \`AMS.exe\`. The hook is installed in process memory after the DLL loads.

## Local consumers

R17 owns these consumers:

- **InventoryConsumer**: owns local craft transaction counters. Blueprint economics will be bound to reconstructed car data separately instead of trusting backend inventory responses.
- **ProfileConsumer**: owns the local set of acquired car IDs.
- **GarageConsumer**: owns local garage status and active car state.
- **PersistenceConsumer**: writes local state immediately after a craft transaction.

## LocalGarageUI

R17 creates a Win32 overlay owned by the game window. It displays:

- current \`car_id\`
- local craft count
- store revision
- current local status
- a **MONTAR LOCAL** button after the garage pointer has been captured

The original synchronization-error popup is unreachable because the original \`BuildCar\` body is not executed.

## Apply

\`\`\`bat
BUILD-R17-LOCAL-EVENT-RUNTIME.cmd
APPLY-R17-LOCAL-EVENT-RUNTIME.cmd
_PACKAGE_PHASE5\RUN-PACKAGE-PHASE5.cmd
\`\`\`

The build requires MSVC x86 (Visual Studio Build Tools, Desktop development with C++).

## Revert

\`\`\`bat
REVERT-R17-LOCAL-EVENT-RUNTIME.cmd
\`\`\`

## Scope of R17.0

R17.0 establishes the new authority boundary: our event runtime, state, consumers and garage UI own the craft transaction.

The next binding is game-wide ownership queries so race/car-selection gates read \`LocalEventStore\` instead of the retired CampaignProfile backend representation.
