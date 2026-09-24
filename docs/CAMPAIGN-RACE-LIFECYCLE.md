# Campaign Race Lifecycle

Campaign Edition owns the post-race transaction while preserving the original race simulation, controls, renderer, audio and in-race HUD.

## Commands

- `CAMPAIGN_OP_BEGIN_EVENT_RACE`
- `CAMPAIGN_OP_FINISH_EVENT_RACE`
- `CAMPAIGN_OP_CANCEL_EVENT_RACE`

## Begin

Inputs:

- `a = event_id`
- `b = car_id` (zero means adapter has not supplied a car id)

The Core validates the local event definition, progression gate and optional Campaign ownership.

It then creates:

`CampaignRaceSession.dat`

The session contains a checksum-protected local `session_id`, event id, car id and starting save revision.

## Finish

Inputs:

- `a = session_id`
- `b = placement`
- `c = stars`
- `d = finish_time_ms`

Transaction:

```text
CampaignRaceSession.dat
        |
        | atomic rename
        v
CampaignRaceSession.consuming
        |
        v
CampaignEvents.dat
        |
        +--> validate event
        +--> calculate local credits
        +--> update best placement/time/stars
        +--> advance local progression
        +--> increment race count
        |
        v
CampaignSave.dat
        |
        +--> save last_completed_race_session_id
        |
        v
delete CampaignRaceSession.consuming
```

## Crash recovery / duplicate protection

If the game stops before the save is committed, the `.consuming` session can be restored to the active session and retried.

If the save was committed but cleanup did not finish, `last_completed_race_session_id` proves that the transaction was already paid. The stale `.consuming` session is discarded instead of awarding the result again.

Repeated calls using a completed session id are idempotent and do not award a second reward.

## Boundary

This subsystem does not change:

- physics;
- race AI;
- renderer;
- models;
- animations;
- audio;
- track loading;
- controls;
- in-race HUD.

Only the race lifecycle/business state after the engine produces a result belongs to Campaign Edition.
