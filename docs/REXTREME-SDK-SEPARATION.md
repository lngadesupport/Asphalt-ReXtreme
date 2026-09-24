# ReXtreme SDK separation contract

## Hard boundary

ReXtremeSDK.exe is a separate downloadable Windows application. It is not bundled into the game and the game must not depend on the editor being installed.

### Creator machine

- ReXtremeSDK.exe
- project files and source assets
- optional Blender integration
- validators/converters
- .rxmod build output

### Player/game machine

- Asphalt ReXtreme
- ReXtreme Mod Runtime only
- installed .rxmod packages

The game-side runtime must never ship editor windows, Blender tooling, authoring UI, source-model converters or SDK project-management code.

## Exchange format

The boundary between SDK and game is the packaged .rxmod plus a versioned runtime API contract.

## Current authoring coverage

The standalone SDK now has contracts/templates for vehicles, tracks, liveries, music, normal/special events, career seasons, Race HUD layouts, replay presets, Photo Mode presets and renderer-audited graphics settings.

Graphics and camera options must not invent capabilities: they are populated only after the original Asphalt Xtreme renderer/camera audit confirms support.
