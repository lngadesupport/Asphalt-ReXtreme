# Asphalt ReXtreme - Source Reconstruction Roadmap

Branch: campaign-edition-win32

## Objective

Build a clean-room functional C++ reconstruction of the shipped x86 client while preserving an explicit mapping back to AMS.exe virtual addresses and file offsets.

This project does not claim to recover Gameloft's original source text, comments, variable names, project files, or server-side PHP that was never shipped with the client.

## R1 - Atlas to source tree

- Consume FULL GAME ATLAS MAX.
- Index every detected function.
- Preserve unresolved functions instead of inventing names.
- Build subsystem subgraphs.
- Seed known classes:
  - GarageBottomBarWidget
  - GS_Garage
  - CraftCarService
  - OfflineBackend
- Keep VA/file provenance in generated metadata.

## R2 - Garage and build flow

Priority reconstruction:
- GarageBottomBarWidget::RegisterButtons (0x00972B90)
- GarageBottomBarWidget::OnBuildPressed (0x00973C90)
- Signal infrastructure around 0x00936BE0 / 0x0096E4B0
- GS_Garage::BuildCar (0x00A87960)
- CraftCar caller (0x0099FF50)
- CraftCar request (0x009A4BA0)
- CraftCar result handler (0x009A48A0)

Goal: reproduce MONTAR locally without dead-server dependency.

## R3 - Profile and persistence

- Profile object model.
- Inventory and blueprint fields.
- Vehicle ownership/unlock state.
- Currency and rewards.
- Save/load serialization.
- Progression mutations performed by backend result handlers.

## R4 - Network contract reconstruction

- Endpoint catalog.
- Request builders.
- Payload serialization.
- Response parsing.
- Error paths/timeouts.
- Replace remote dependencies with OfflineBackend contracts.

## R5 - UI/state reconstruction

- Screen/state classes from RTTI/vtables.
- Widgets, templates, callbacks and signal graph.
- Career/garage/race navigation.
- Dialogs and tutorials.

## R6 - Broad functional coverage

- Iterate unresolved function shards.
- Type and name functions only when evidence supports it.
- Maintain confidence/provenance metadata.
- Build a standalone reconstructed client architecture where practical.

## Provenance rule

Every reconstructed function should retain:
- original VA,
- original file offset when known,
- vtable slot/class when known,
- relevant string/RTTI evidence,
- confidence level,
- unresolved dependencies.

No guessed semantic name should be presented as original unless the binary actually contains that name.
