# ReXtreme SDK Blender Tools

Install the `rextreme_sdk_blender` folder/add-on in Blender.

The add-on is optional and external to the game. It helps prepare Blender content for the standalone ReXtreme SDK.

Current foundation:
- mark vehicle parts, collision meshes and track markers;
- mark start/finish/checkpoint/respawn/AI/replay-camera/audio-zone objects;
- export a GLB plus `.rxscene.json` metadata;
- preserve `rx_*` custom properties for the SDK conversion pipeline.

The final ReXtreme runtime format is produced by ReXtremeSDK.exe, not by Blender itself.
