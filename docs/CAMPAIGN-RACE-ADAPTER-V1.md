# Campaign Race Adapter v1

This patch connects the preserved race GUI lifecycle to the rebuilt Campaign race lifecycle.

It is intentionally inactive unless both authoritative data files exist:

- `CampaignEvents.dat`;
- `CampaignObjectives.dat`.

## BEGIN hook

Verified common `GameModeGUIBase` constructor tail:

- preferred VA: `0x00C7E73B`;
- file offset: `0x0087DB3B`;
- original bytes: `8B C3 8B 4D F4`.

At that point:

- `EBX = GameModeGUIBase*`;
- `GameModeGUIBase+0x14 = GameModeBase*`;
- the GameModeBase event source is already attached.

The adapter calls selector `0xC0DEB001`, which invokes `CampaignBeginRaceFromGui`.

## FINISH hook

Verified common result-screen creation tail:

- preferred VA: `0x00CC8828`;
- file offset: `0x008C7C28`;
- original bytes:
  `8B 75 EC C7 45 FC FF FF FF FF`.

Before those instructions execute, `ESI` still holds `GameModeGUIBase*`.

The adapter calls selector `0xC0DEF001`, which invokes `CampaignFinishRaceFromGui`, then restores the two overwritten original instructions and resumes at `0x00CC8832`.

## Separate code caves

BEGIN:

- VA `0x01109DD5`;
- file offset `0x00D091D5`;
- 43 bytes of verified `CC` padding.

FINISH:

- VA `0x010E9BA5`;
- file offset `0x00CE8FA5`;
- 43 bytes of verified `CC` padding.

Both were checked for direct call/jump references in the baseline disassembly.

## ASLR

Both stubs are position-independent.

They use `call $+5 / pop eax` to recover the runtime position and derive the already-imported IGP gateway IAT slot. No absolute process address is embedded in the patch.

## Authority boundary

The hooks do not alter:

- physics;
- race AI;
- renderer;
- models;
- animations;
- audio;
- track loading;
- controls;
- in-race HUD.

They also do not reuse original reward/progression synchronization.

The adapter reads finalized engine metrics and passes them to Campaign Core. Campaign Objectives, Campaign Events and Campaign Save remain authoritative.
