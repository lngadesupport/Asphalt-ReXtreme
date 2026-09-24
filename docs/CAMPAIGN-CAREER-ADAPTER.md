# Campaign Career Adapter

This adapter is the thin boundary between the preserved Asphalt Xtreme race/client layer and Campaign Core.

It does not own rewards or progression.

## Verified PreCareerEventRequest layout

The original serializer at `0x00DC6EA0` proves:

- `request + 0x40 = event_id` via literal `&event_id=%d`;
- `request + 0x44 = car_id` via literal `&car_id=%d`.

`CampaignBeginCareerFromPreRequest` converts those fields into:

`CAMPAIGN_OP_BEGIN_EVENT_RACE`

and returns the local Campaign session id.

## Verified PostCareerEventRequest layout

The original serializer at `0x00D18890` proves:

- `+0x40 = car_id`;
- `+0x64 = event_id`;
- `+0x68 = star1`;
- `+0x69 = star2`;
- `+0x6A = star3`;
- `+0x78 = position_in_race`;
- `+0x7C = race_time`.

Position and race time use the client's address-XOR encoding:

```text
decoded = encoded XOR address_of_field XOR *(AMS_base + 0x0153A1C8)
```

The adapter reproduces only that decoding and sends:

`CAMPAIGN_OP_FINISH_EVENT_RACE`

with `session_id=0`, meaning the Core resolves the active checksum-protected local session.

## Authority boundary

The adapter reads legacy client state only as input.

It does not use:

- post_event_score.php;
- pre_career_race.php;
- remote race_token authority;
- remote reward result;
- remote progression result.

Campaign Core remains authoritative for rewards, stars, completion state and persistence.
