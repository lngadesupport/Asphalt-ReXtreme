# ReXtreme SDK

**ReXtreme SDK is a standalone Windows application.** It is not embedded into ReXtreme or Asphalt Xtreme.

- Editor/application: `ReXtremeSDK.exe`
- Authoring output: `.rxmod`
- Game side: only the ReXtreme Mod Runtime/loader needed to consume `.rxmod`

## Foundation implemented

- WPF editor shell with project tree, inspector, output console and tabbed tools;
- project creation/opening;
- content validation;
- deterministic `.rxmod` ZIP packaging with SHA-256 package index;
- vehicle authoring foundation with original-category selection and original physics-profile inheritance;
- game-style normalized performance bars for speed, acceleration, handling and nitro;
- 3D asset import catalog and first OBJ viewport preview with mouse rotation;
- music import catalog for WAV/FLAC/OGG/MP3/AAC/M4A;
- event template creation;
- career-season template creation;
- Race HUD layout template creation;
- self-contained Windows x64 publishing configuration.

## Architecture

The SDK may ship optional integrations such as Blender tools, but the SDK editor itself remains a separate downloadable application. The game never needs the SDK installed to run mods.
