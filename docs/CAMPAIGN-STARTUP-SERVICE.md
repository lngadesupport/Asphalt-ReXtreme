# Campaign Startup Service

The Gameloft splash is preserved as frontend presentation only.

Campaign Edition does not rely on the original online/profile startup state machine for authority.

## Runtime states

```text
COLD
  |
  | CampaignStartupBegin()
  v
PROFILE_READY
  |
  | CampaignStartupEnterLobby()
  v
LOBBY_READY
```

Failure is explicit and local:

```text
FAILED
```

## Authority

Campaign startup owns:

- local save reload;
- local profile readiness;
- local event-bus reset;
- lobby readiness;
- startup state.

The original frontend owns only:

- Gameloft splash rendering;
- age/onboarding presentation;
- visual transition to the lobby.

## Explicit exclusions

Startup does not touch:

- garage ownership;
- generic STL/container membership;
- Career state;
- Store;
- Upgrade state;
- network state machines;
- GlobalSync;
- remote profile callbacks.

Ownership is exposed as:

```text
CampaignFrontendIsOwned(car_id)
```

and must only be called by migrated car consumers. The old experiment that replaced the generic `vector<int>::contains` at `0x00E530E0` is retired permanently.

## Safety invariant

No Garage/ownership code executes before a Garage/car consumer explicitly invokes it.

This invariant exists specifically to prevent startup regressions on the Gameloft splash.
