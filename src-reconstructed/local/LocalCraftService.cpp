#include "LocalCraftService.h"

namespace rextreme::offline {

SharedPair LocalCraftService::CreateOperation(
    void* coordinator,
    const CraftInput& input) {
    (void)coordinator;
    (void)input;

    // Runtime bridge TODO:
    // Reuse the client-created CraftCar operation produced before the old
    // 0x009A00ED network call. Do not fabricate its object layout.
    //
    // The binary-side R16 bridge supplies this pair after reconstructing the
    // exact handoff from CraftCar_Caller.
    return {};
}

bool LocalCraftService::CompleteAfterListenerRegistration(
    void* gs_garage,
    SharedPair operation,
    const CraftInput& input) {
    if (gs_garage == nullptr || operation.object == nullptr) {
        return false;
    }

    if (!ApplyCampaignTransaction(input)) {
        return false;
    }

    return DispatchGarageSuccess(gs_garage, operation);
}

bool LocalCraftService::ApplyCampaignTransaction(const CraftInput& input) {
    // Contract:
    //   - validate blueprint balance >= blueprint price;
    //   - debit blueprint inventory locally;
    //   - mark input.car_id owned;
    //   - persist through the reconstructed CampaignProfile/Inventory layer.
    //
    // Exact original writers are being bound by the R16 runtime bridge.
    return input.car_id != 0 &&
           input.blueprint_balance >= input.blueprint_price;
}

bool LocalCraftService::DispatchGarageSuccess(
    void* gs_garage,
    SharedPair operation) {
    (void)gs_garage;
    (void)operation;

    // Original result dispatch contract reconstructed from 0x009A48A0:
    // status = 0, context is an 8-byte shared pair, then listener virtual +4.
    //
    // The runtime bridge will invoke the original listener only after it has
    // been registered by GS_Garage.
    return false;
}

} // namespace rextreme::offline
