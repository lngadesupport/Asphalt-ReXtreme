#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct RexContentVehicle {
    uint32_t vehicle_id;
    int unlocked_by_default;
    int has_recipe;
    uint32_t blueprint_id;
    uint32_t blueprint_cost;
} RexContentVehicle;

typedef struct RexContent {
    const RexContentVehicle* vehicles;
    uint32_t vehicle_count;
} RexContent;

void RexContent_Init(
    RexContent* content,
    const RexContentVehicle* vehicles,
    uint32_t vehicle_count
);

const RexContentVehicle* RexContent_FindVehicle(
    const RexContent* content,
    uint32_t vehicle_id
);

#ifdef __cplusplus
}
#endif
