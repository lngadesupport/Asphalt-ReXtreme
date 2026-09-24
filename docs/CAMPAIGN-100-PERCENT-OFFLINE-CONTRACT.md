# Campaign Edition — 100% Offline Contract

This document is normative.

## Product rule

Campaign Edition is a local-only single-player game.

No feature may require:

- internet access;
- a remote backend;
- multiplayer or matchmaking;
- cloud profile state;
- remote configuration;
- remote events;
- server rewards;
- IAP;
- advertising;
- social services;
- leaderboards;
- push notifications;
- telemetry as a gameplay dependency;
- network retry flows.

The original game is preserved only where useful as presentation/gameplay frontend.

## Allowed original code

Original code may remain only when it is acting as:

- rendering;
- animation;
- HUD/presentation;
- menu navigation/presentation;
- local input plumbing;
- race physics/simulation;
- audio/visual asset playback;
- local screen transition logic.

It may not remain authoritative for campaign/business state.

## Required Campaign Edition authorities

The following authorities must be local Campaign Edition code:

- Startup/Profile
- Save/Persistence
- Economy
- Inventory
- Garage
- Ownership
- Vehicle acquisition/crafting
- Career progression
- Race rewards
- Objectives
- Events
- Upgrades
- Pro-Kits
- Store
- Tutorial progression
- UI service state
- Feature availability
- Local notifications
- Local event synchronization

## Explicitly retired

These original systems are not valid fallbacks:

- GlobalSync
- CraftCar remote flow
- remote ownership authority
- HTTP backend scripts
- remote profile sync
- multiplayer
- matchmaking
- remote leaderboards
- social/Facebook/MSN
- Store/IAP
- rewarded advertising
- remote event scheduler
- push
- cloud save
- online-required popup/retry state machines

## No simulated online

Campaign Edition must not pretend that a server replied.

A migrated flow must be:

```text
frontend action
  -> local Campaign service
  -> local state mutation
  -> local persistence
  -> local Campaign event
  -> frontend refresh/presentation
```

It must not be:

```text
frontend action
  -> fake request
  -> fake server callback
  -> legacy online completion
```

## Completion gate

A subsystem is complete only when:

1. its authoritative state is local;
2. no server/network result is required;
3. it survives restart;
4. no legacy online fallback can mutate that state;
5. its frontend consumes local Campaign state;
6. offline use is indistinguishable from normal intended single-player use.

The product is not "100% offline" until every unresolved legacy online authority is eliminated.
