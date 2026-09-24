# ReXtreme SDK — implementation progress

## Distribution model

ReXtreme SDK is a standalone, separately downloadable Windows x64 application.

- Creator tool: ReXtremeSDK.exe
- Output: .rxmod packages
- Game side: ReXtreme Mod Runtime only
- The game does not embed the SDK/editor.

## Implemented foundation

### Standalone editor
- WPF editor shell
- project tree
- inspector/dependency manager
- validation output
- self-contained single-file Windows publishing
- CI artifact ZIP

### Mod/package system
- manifest and namespaced IDs
- dependency declarations
- deterministic .rxmod packaging
- SHA-256 package index
- package verification

### Vehicle authoring
- original Asphalt Xtreme category/archetype registry foundation
- original physics-profile inheritance
- game-style performance bars
- original-registry import/validation
- 3D asset association

### 3D / Blender
- Blender discovery through BLENDER_PATH or installed Blender
- BLEND and common interchange-format conversion bridge
- canonical GLB output where Blender can import the source
- generated OBJ preview for the WPF viewport
- Blender addon foundation
- track-bundle import foundation

### Content editors
- normal race/event definitions
- Special Events
- career seasons / append / branch modes
- track metadata
- livery/paint layers
- Race HUD layout and bindings
- music library/import with title, artist and context
- replay presets
- Photo Mode presets
- graphics capability presets restricted to original-renderer audit results

### Race HUD
Draggable foundation components currently include:
- position
- speed
- nitro
- lap
- timer
- minimap
- objective

### Livery
- base paint color
- imported texture/decal layer
- texture asset copy into project
- layered JSON definition

### Replay / Photo
Replay authoring contract includes timeline, playback speeds, frame-step, event markers, camera types, target switching, HUD toggle and Photo Mode integration.

Photo Mode contract supports pause-menu and replay-pause entry points, camera/FOV values and screenshot/HUD controls. Renderer effects intentionally remain empty until confirmed by the original engine.

## Hard constraints

1. No replacement racing physics is introduced.
2. Custom vehicles derive from verified original Asphalt Xtreme vehicle profiles.
3. Graphics options are never invented; they must come from renderer/runtime audit.
4. In-game ReXtreme UI uses the original game's visual language/assets; SDK UI is an external editor.
5. The SDK is not required to play the game or use installed mods.

## Next high-value implementation blocks

- richer 3D viewport (GLB materials, cameras, lighting, gizmos)
- visual track nodes: checkpoints, start grid, respawn, AI routes, shortcuts, replay cameras
- visual livery decal transform tools
- full Career graph composer
- Special Event graph/editor
- HUD component palette, scaling/opacity/anchors/aspect-ratio variants
- original UI asset catalog
- runtime .rxmod VFS/load-order bridge
- runtime music bridge
- replay recorder/player hooks
- Photo Mode runtime camera bridge
- renderer/camera capability audit feeding graphics/FOV UI
