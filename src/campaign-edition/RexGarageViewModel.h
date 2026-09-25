#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum RexGarageBuildStatus {
    REX_GARAGE_BUILD_NO_SELECTION = 0,
    REX_GARAGE_BUILD_OWNED = 1,
    REX_GARAGE_BUILD_LOCKED = 2,
    REX_GARAGE_BUILD_UNAVAILABLE = 3,
    REX_GARAGE_BUILD_NEEDS_BLUEPRINTS = 4,
    REX_GARAGE_BUILD_READY = 5
} RexGarageBuildStatus;

typedef struct RexGarageViewModelInput {
    uint32_t selected_vehicle_id;
    int owned;
    int unlocked;
    int has_recipe;
    uint32_t blueprint_balance;
    uint32_t blueprint_cost;
} RexGarageViewModelInput;

typedef struct RexGarageViewModel {
    uint32_t selected_vehicle_id;
    int owned;
    int unlocked;
    int build_enabled;
    uint32_t blueprint_balance;
    uint32_t blueprint_cost;
    RexGarageBuildStatus build_status;
} RexGarageViewModel;

void RexGarageViewModel_Build(
    const RexGarageViewModelInput* input,
    RexGarageViewModel* output
);

#ifdef __cplusplus
}
#endif
