# Frontend-Only Migration Matrix

This matrix is normative for Campaign Edition.

## Preserved from the original game

| Area | Policy |
|---|---|
| 3D rendering | PRESERVE |
| UI layouts/assets | PRESERVE |
| menu animation/presentation | PRESERVE |
| HUD presentation | PRESERVE |
| input plumbing | PRESERVE |
| race presentation | PRESERVE |
| physics/race engine | PRESERVE while stripped of service authority |
| audio/visual assets | PRESERVE |
| screen transitions | PRESERVE where they do not require online state |

## Replaced by Campaign Edition

| Area | Replacement | State |
|---|---|---|
| frontend/business boundary | CampaignFrontendBridge | ACTIVE DEVELOPMENT |
| event synchronization | CampaignEventBus | IMPLEMENTED |
| online policy | CampaignOnlinePolicy | IMPLEMENTED |
| campaign notices/UI policy | CampaignUiService | IMPLEMENTED |
| typed domain facade | CampaignServices | IMPLEMENTED |
| profile state | Campaign Core local state | IMPLEMENTED / frontend cutover pending |
| economy | Campaign Core | IMPLEMENTED |
| ownership | CampaignServices/Garage | IMPLEMENTED / frontend cutover pending |
| crafting/acquisition | CampaignServices/Garage | IMPLEMENTED / frontend cutover pending |
| career progression | CampaignServices/Career | IMPLEMENTED / frontend cutover pending |
| race rewards | CampaignServices/Career | IMPLEMENTED / frontend cutover pending |
| upgrades/pro-kits | CampaignServices/Upgrade | DATA BLOCKED where UI map unresolved |
| store | CampaignServices/Store | LOCAL CATALOG / content population pending |
| save/persistence | CampaignSave.dat | IMPLEMENTED |
| local events | CampaignEvents.dat | IMPLEMENTED |

## Retired original systems

These are never authoritative in the target architecture:

- profile/cloud synchronization;
- GlobalSync transport;
- connection retry state machines;
- online-required popups;
- IGP promotion/store web flows;
- Store/IAP/licensing;
- reward advertising;
- push notifications;
- social/Facebook/MSN;
- leaderboard services;
- multiplayer services;
- telemetry as a gameplay dependency;
- remote config;
- remote event schedule;
- remote rewards;
- HTTP backend scripts;
- remote ownership/crafting;
- remote upgrade transactions;
- online purchase requests.

## Deprecated experiments

The following generations were diagnostic/migration steps and are not the final architecture:

- Profile Adapter v1/v2;
- Offline Surface v4/v5;
- Offline Lobby v6/v7;
- global GS_MessagePopup hooks;
- broad GlobalSync completion hooks;
- global ownership-function replacement.

Their findings remain useful, but the target runtime replaces the original consumer boundary instead.

## Cutover order

1. Boot/Profile/Lobby
2. UI notice/event synchronization
3. Garage/ownership/build
4. Economy
5. Career/race result/progression
6. Upgrades/pro-kits
7. Store
8. ads/IAP/social/push/telemetry retirement
9. remove package/service compatibility shims
10. offline audit: zero unresolved service consumers

## Definition of done

Campaign Edition is complete only when the original frontend can be used with networking disabled and every non-frontend authority comes from Campaign Edition code.
