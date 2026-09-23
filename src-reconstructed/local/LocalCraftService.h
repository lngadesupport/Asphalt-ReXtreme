#pragma once
#include <cstdint>

namespace rextreme::offline {

struct SharedPair {
    void* object = nullptr;
    void* control = nullptr;
};

struct CraftInput {
    std::int32_t car_id = 0;
    std::int32_t blueprint_id = 0;
    std::int32_t blueprint_balance = 0;
    std::int32_t blueprint_price = 0;
};

enum class CraftStatus : std::int32_t {
    Success = 0
};

struct CraftCompletion {
    CraftStatus status = CraftStatus::Success;
    SharedPair context{};
};

// Clean-room replacement for the removed CraftCar backend boundary.
//
// Runtime integration is intentionally split:
//  1. CreateOperation() returns an operation compatible with GS_Garage.
//  2. CompleteAfterListenerRegistration() performs the local transaction
//     only after GS_Garage has installed its +0x298 listener.
class LocalCraftService final {
public:
    static SharedPair CreateOperation(void* coordinator, const CraftInput& input);

    static bool CompleteAfterListenerRegistration(
        void* gs_garage,
        SharedPair operation,
        const CraftInput& input);

private:
    static bool ApplyCampaignTransaction(const CraftInput& input);
    static bool DispatchGarageSuccess(void* gs_garage, SharedPair operation);
};

} // namespace rextreme::offline
