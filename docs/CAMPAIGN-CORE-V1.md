# Campaign Core v1

Campaign Core replaces the old vehicle build and ownership backend while keeping the original garage presentation.

Runtime boundary:
- IGPLib_x86.dll remains a /NOENTRY DLL. Nothing runs at process startup.
- GS_Garage::BuildCar is replaced by a tiny AMS trampoline.
- The old CraftCarRequestImpl, network request, JSON result handler, event synchronizer and original build observer are not executed.
- The old car-id membership query used by the garage is replaced by CampaignIsOwned(car_id).

Authoritative state:
%LOCALAPPDATA%\Packages\<PFN>\LocalState\CampaignEdition\campaign_state.bin

The state contains a version, revision, Campaign currencies, owned car IDs and a new Campaign inventory table.

The original garage UI and its signal wiring are preserved. Campaign Core uses only the garage UI refresh virtual after a local craft.