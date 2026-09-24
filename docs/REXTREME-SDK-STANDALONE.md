# ReXtreme SDK — standalone application

The ReXtreme SDK is deliberately separated from the game.

## Distribution boundary

### ReXtremeSDK.exe
Downloaded separately by creators. Contains the project editor, content authoring tools, validators, asset import/conversion pipeline, previews, packaging and optional DCC integrations.

### ReXtreme game
Does not contain the SDK editor. It contains only the minimum ReXtreme Mod Runtime needed to discover, validate and load installed `.rxmod` packages.

### .rxmod
Portable expansion/mod package produced by the SDK.

This boundary allows ordinary players to install/run ReXtreme without developer tooling, while mod creators can download a dedicated SDK.

## Current foundation

The first executable editor includes project creation/opening, validation, `.rxmod` builds, vehicle authoring with original profile inheritance, an initial 3D viewport, music import, event/career templates and Race HUD authoring foundations.

The CI workflow publishes a self-contained Windows x64 ZIP containing `ReXtremeSDK.exe`.
