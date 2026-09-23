# Offline Replacement Architecture

## Project rule

Asphalt ReXtreme: Campaign Edition no longer treats the removed Gameloft backend as a dependency that must be emulated at every call site.

When an original subsystem depends on dead online infrastructure, incomplete remote state, or a code path that cannot complete offline, we replace that subsystem with a local implementation while preserving the smallest stable client-facing contract around it.

The client UI, gameplay, progression screens, object layouts, callback interfaces and save/profile behaviors should remain original wherever they are still usable.

## Replacement order

1. Preserve original caller/UI code.
2. Identify the smallest broken online-facing boundary.
3. Reconstruct its inputs, outputs, ownership rules and callback contract.
4. Implement a local replacement with that contract.
5. Route only that subsystem to the replacement.
6. Keep global connectivity disabled.
7. Validate persistence and UI refresh.
8. Remove obsolete compatibility patches once their replacement supersedes them.

## Current first subsystem: CraftCar

Confirmed runtime path after R15:

```
GarageBottomBarWidget::Build callback
  -> SignalInvoke
  -> GS_Garage::BuildCar
  -> CraftCar_Caller
```

The old network path beyond CraftCar_Caller is not required for Campaign Edition.

### Original contract that must be preserved

CraftCar_Caller:

- receives a coordinator object as `this`;
- validates operation slots at +0x70/+0x80/+0x90/+0xA0/+0xB0/+0xC0;
- builds and returns a shared operation pair;
- GS_Garage stores the returned pair at +0x3AC/+0x3B0;
- GS_Garage registers listener `&GS_Garage+0x298` on the operation.

Original CraftCar result dispatch:

- normalized success status is 0;
- operation/result context pair is copied from +0x24/+0x28;
- listeners live in the vector [+0x44,+0x48);
- callback virtual slot +0x04 receives the status plus an 8-byte shared context;
- GS_Garage listener slot +0x04 resolves to 0x00AA4D00.

### R16 design

R16 introduces a local CraftCar service with two stages:

```
CreateLocalCraftOperation()
  -> return compatible shared operation to GS_Garage

GS_Garage registers its listener

CompleteLocalCraftOperation(status=0)
  -> mutate local campaign/profile state
  -> consume required blueprint balance
  -> mark car owned
  -> dispatch original listener contract
  -> let original garage refresh/UI code run
```

Completion MUST happen after listener registration. An immediate completion inside the old network-call site is invalid because GS_Garage has not registered +0x298 yet.

## Replacement registry

| Original subsystem | Status | Replacement |
| --- | --- | --- |
| Global connectivity | disabled | Offline policy |
| No-internet popup path | bypassed | Local UI policy |
| CraftCar request/backend | R16 active reconstruction | LocalCraftService |
| CraftCar result transport | R16 active reconstruction | Local completion dispatcher |
| Profile ownership mutation | reuse original/local writer where safe | CampaignProfile |
| Blueprint debit | reuse original/local writer where safe | CampaignInventory |
| Backend sync keys | obsolete for offline operation | Local persistence |
| Store/backend purchases | pending | LocalStoreService |
| Time-limited events | pending | LocalEventService |
| Remote rewards | pending | LocalRewardService |

## Safety rules for binary patches

Every runtime patch must:

- verify expected bytes before writing;
- refuse unknown bytes;
- create a backup;
- be ASLR-safe when it contains control flow;
- keep APPLY and REVERT paths;
- avoid writable state in executable-only PE sections;
- prefer replacing one boundary over forcing many downstream guards.

## Goal

The target is functional reconstruction, not literal recovery of Gameloft server source.

A completed subsystem is one whose user-visible behavior, persistence, progression effects and callback/UI contract work locally without the original backend.
