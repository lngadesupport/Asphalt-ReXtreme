# CampaignGarage v2

CampaignGarage v2 is the first production AMS integration for the literal Campaign Edition rebuild.

## What survives from the original garage

Only the visual/input layer:

- original garage screen;
- original MONTAR button;
- original selected-car presentation;
- original garage animations/widgets;
- original visual refresh function.

## What is retired

The MONTAR path no longer executes the old `GS_Garage::BuildCar` body.

Therefore it cannot reach:

- `CraftCar_Caller`;
- `CraftCarRequestImpl`;
- remote CraftCar request;
- remote JSON result handler;
- CraftCar listener completion;
- original event synchronization.

## MONTAR route

```text
original garage MONTAR signal
          |
          v
GS_Garage::BuildCar entry
          |
          | JMP rel32
          v
Campaign position-independent AMS gateway
          |
          | selector 0xC0DEC0DE
          v
IGPLib_x86 Campaign Core v2
          |
          v
CampaignCraftInvoke(GS_Garage*)
          |
          +--> selected car via GS_Garage+0x2D4 / selected+0xC0
          +--> Campaign ownership transaction
          +--> CampaignSave.dat
          +--> garage visual refresh
          |
          v
return directly to original UI caller
```

The selected-car offsets are UI adapter metadata only. `0x00D805F0`, the original selected-car helper, is exactly `mov eax,[ecx+0xC0]; ret`, which validates the adapter.

## Ownership route

The original membership function at `0x00E530E0` is a concrete vector membership check over car ids.

CampaignGarage v2 replaces its entry with:

```text
car_id pointer
     |
     v
Campaign position-independent gateway
     |
     | selector 0xC0DE0A11
     v
CampaignIsOwned(car_id)
```

This is not the previously rejected `0x00A938A0` lookup guess.

## ASLR safety

No new absolute process address is embedded in the AMS patch.

The gateway uses `call $+5 / pop eax` to obtain its runtime instruction address, then derives the imported IGP gateway address relative to that position.

The two AMS redirects are rel32 JMPs.

## Stage 1 semantics

CampaignGarage v2 intentionally treats MONTAR as direct local acquisition. This is a wiring/authority milestone, not the final economy.

No fake blueprint recipe is invented.

CampaignGarage v3 will bind MONTAR to the new Campaign Vehicle Catalog:

```text
car_id
  -> acquisition type
  -> blueprint/item id
  -> cost
  -> unlock requirements
  -> Campaign Core atomic craft/purchase
```

## Old experiments

The applicator retires known R15, Phase39 and Phase48 CraftCar experiments when their exact byte signatures are present.

It preserves the ten protected engine/presentation subsystems.
