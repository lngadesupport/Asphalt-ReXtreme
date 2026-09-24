# Campaign Edition — Frontend-Only Original Code Rule

This document is normative and supersedes older transitional architecture notes.

## Absolute rule

Campaign Edition may reuse original Asphalt Xtreme code only for frontend presentation.

Allowed original responsibilities:
- visual layouts;
- widgets and controls;
- textures, models, fonts and audio assets;
- animation and transitions;
- rendering;
- visual HUD;
- presentation-only input plumbing.

Everything else must be Campaign Edition code.

## Forbidden original responsibilities

Original code must not remain authoritative or participate as a required step in:
- startup state;
- profile;
- tutorial state/progression;
- garage state;
- ownership;
- build/craft;
- economy;
- inventory;
- upgrades;
- pro-kits;
- store;
- career;
- objectives;
- events;
- race setup/results/rewards;
- save/load;
- feature availability;
- online/offline decisions;
- multiplayer/matchmaking;
- ads/IAP/social/cloud/push/leaderboards;
- remote configuration;
- telemetry-dependent gameplay;
- callbacks/completions/listeners/signals used as gameplay state machines.

## No legacy-flow reuse

A legacy flow may be reverse engineered for observation only.

It must not be used as:
- a fallback;
- a completion mechanism;
- a state transition mechanism;
- an ownership source;
- a tutorial source;
- a reward source;
- a synchronization mechanism;
- a fake local server protocol.

## Required runtime shape

```text
ORIGINAL FRONTEND
    |
    | user intent / visual input
    v
CampaignFrontendPort
    |
    v
CampaignApplication
    |
    +-- CampaignStartup
    +-- CampaignTutorial
    +-- CampaignGarage
    +-- CampaignEconomy
    +-- CampaignCareer
    +-- CampaignObjectives
    +-- CampaignEvents
    +-- CampaignUpgrades
    +-- CampaignStore
    +-- CampaignSave
    |
    v
CampaignViewModel
    |
    v
ORIGINAL FRONTEND RENDERING
```

The frontend is a view. It never owns gameplay truth.

## Migration rule

Any module that calls an original gameplay/business function is transitional and cannot be marked FINAL.

A subsystem is FINAL only when:
1. its input is a frontend intent;
2. all state transitions are Campaign Edition code;
3. persistence is Campaign Edition code;
4. output is a frontend view model;
5. no original gameplay/business callback or state machine is required.

## Current status

The existing Boot/Garage/Career adapters are transitional reverse-engineering scaffolding.
They are not the final architecture under this rule.
