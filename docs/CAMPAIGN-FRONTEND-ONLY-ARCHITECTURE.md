# Campaign Edition — Frontend-Only Architecture

## Project rule

The original Asphalt Xtreme codebase is retained only as a presentation/gameplay frontend where it remains useful:

- rendering;
- UI layout and animation;
- menu navigation presentation;
- HUD presentation;
- input plumbing;
- race rendering/physics integration where it does not own campaign/business state;
- asset loading required by the preserved frontend.

All service, business, persistence, progression and online-era authority is replaced by Campaign Edition code.

## Forbidden legacy authority

The following original subsystems are not authoritative in Campaign Edition and must not be used as backends:

- profile/cloud synchronization;
- connectivity state machines;
- GlobalSync/network synchronizers;
- remote configuration;
- IAP/Store/licensing;
- advertising/reward ads;
- social/Facebook/MSN integrations;
- leaderboards;
- multiplayer services;
- push notifications;
- telemetry used as a gameplay dependency;
- remote event scheduling;
- remote rewards;
- remote garage ownership;
- remote crafting;
- remote upgrade/pro-kit transactions;
- online purchase requests;
- online connection/retry popups;
- backend HTTP transports;
- service-specific callbacks whose completion depends on a remote response.

## Runtime architecture

```text
Original frontend
  |
  | UI action / gameplay observation
  v
CampaignFrontendBridge
  |
  | typed request
  v
CampaignRuntime
  |
  +--> CampaignProfileService
  +--> CampaignEconomyService
  +--> CampaignGarageService
  +--> CampaignCareerService
  +--> CampaignUpgradeService
  +--> CampaignStoreService
  +--> CampaignEventService
  +--> CampaignObjectiveService
  +--> CampaignUiService
  +--> CampaignPersistence
  |
  v
CampaignEventBus
  |
  | typed frontend event
  v
Original frontend refresh/presentation only
```

## Frontend boundary

The frontend may:

- ask for current local state;
- issue a typed user action;
- display a local result;
- display a local campaign notice;
- observe race results;
- refresh a screen from local state.

The frontend may not:

- decide ownership;
- decide balances;
- decide rewards;
- decide progression;
- perform a network request;
- wait for a network callback;
- show an online-required error;
- mutate campaign state outside CampaignRuntime.

## Online policy

Network authority is permanently disabled.

```text
CampaignOnlineIsNetworkAllowed() == 0
```

Legacy service requests are classified and retired by `CampaignOnlinePolicy`.

Connection-error UI is not recreated. In Campaign Edition, a network dependency is a retired implementation detail, not a user-facing error state.

## UI policy

`CampaignUiService` owns Campaign Edition notices.

Legacy online UI kinds are suppressed at the service boundary:

- connection error;
- retry connection;
- cloud sync;
- online required.

Normal campaign notices are emitted through `CampaignEventBus` and rendered by the preserved frontend.

## Migration strategy

Do not globally hook generic UI functions.

Instead:

1. identify one original consumer boundary;
2. replace its business call with a typed CampaignFrontendBridge request;
3. return a local event/result;
4. preserve only the original presentation/update callback where safe;
5. delete/retire the legacy compatibility patch for that subsystem.

## Completion gate

A subsystem is complete only when:

- no remote transport is reachable;
- no remote callback is required;
- no connection popup can be produced by that subsystem;
- state is persisted locally;
- the frontend updates from Campaign Edition state;
- behavior survives restart;
- the old backend path is not an alternate authority.

The final build is not considered fully offline while any legacy service consumer is unresolved.
