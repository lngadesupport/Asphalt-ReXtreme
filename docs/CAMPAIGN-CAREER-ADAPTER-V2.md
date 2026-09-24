# Campaign Career Adapter v2

This adapter removes the original career pre/post service requests from the Campaign Edition authority path.

## Verified pre-race boundary

The original flow is:

```text
GS_BoosterSelect
  +0x680 -> event_id
  +0x684 -> car_id
        |
        v
CareerServer
  +0xF8 -> event_id
  +0xFC -> car_id
        |
        v
PreCareerEventRequest
```

The mapping is proven by the original Pre serializer:

- request `+0x40` -> `&event_id=%d`;
- request `+0x44` -> `&car_id=%d`.

Campaign Edition patches `CareerServer` at preferred VA `0x00A05690`.

The replacement:

1. passes `event_id + car_id` to selector `0xC0DEB072`;
2. Campaign Core creates/reuses the local race session;
3. remote race-token fields `CareerServer+0xE0/+0xE4` are zeroed;
4. the existing local listener transition at `0x00A1A540` is invoked;
5. no `PreCareerEventRequest` is constructed.

The retired Pre factory body at `0x009DE120` is reused only as adapter code space.

## Verified post-race boundary

The original Post request was created at `0x009DDFA0` and serialized by `0x00D18890`.

Both have a single direct caller in this build.

Campaign Edition:

- replaces the Post factory with a null shared-pointer return;
- changes the caller at `0x00A05650` to pass `CareerServer*`;
- repurposes `0x00D18890` as a local listener completion notifier;
- never creates or serializes `PostCareerEventRequest`.

The notifier performs only the local completion-state transition and the CareerServer listener `vfunc(+0x24)` dispatch. It does not parse or apply backend rewards/profile state.

## Campaign-owned result evaluation

The result itself is not taken from the original Post response.

A read-only result adapter uses finalized engine metrics and calls Campaign Core. Campaign Core evaluates `CampaignObjectives.dat`, calculates Campaign stars, applies `CampaignEvents.dat` rewards/progression and persists `CampaignSave.dat`.

The broad v1 BEGIN hook is retired when its exact byte signature is present. The engine-metric FINISH hook is retained.

## ResultInfo evidence

The original `ResultInfo` / Post copy path was mapped as validation:

- `+0x00` car_id;
- `+0x24` event_id;
- `+0x28/+0x29/+0x2A` original star booleans;
- `+0x38` position;
- `+0x3C` race time;
- `+0x40` race distance.

Position and race time use the client XOR storage form:

```text
plain = encoded ^ field_address ^ key_u32
key_u32 RVA = 0x0153A1C8 from AMS base
```

Campaign Edition does not use the original star booleans as authority; they remain reverse-engineering validation only.

## Guard conditions

The patcher refuses to apply unless:

- `AMS.exe` matches all verified original service-site bytes;
- `CampaignEvents.dat` exists;
- `CampaignObjectives.dat` exists;
- the rebuilt no-entry Campaign Core is available.

Unknown or partial states are not force-patched.

## Preserved systems

No changes are made to physics, race AI, renderer, models, animations, audio, track loading, controls, in-race HUD, or the visual garage UI.
