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

#define REX_CONTENT_VERSION 2u
#define REX_CONTENT_MAX_VEHICLES 128u
#define REX_CONTENT_MAX_INITIAL_BALANCES 256u
#define REX_CONTENT_MAX_STARTER_OWNED 128u

typedef struct RexContentInitialBalance {
    uint32_t blueprint_id;
    uint32_t amount;
} RexContentInitialBalance;

typedef struct RexContent {
    const RexContentVehicle* vehicles;
    uint32_t vehicle_count;
    RexContentVehicle loaded_vehicles[REX_CONTENT_MAX_VEHICLES];
    uint32_t initial_balance_count;
    RexContentInitialBalance initial_balances[
        REX_CONTENT_MAX_INITIAL_BALANCES
    ];
    uint32_t starter_owned_count;
    uint32_t starter_owned_vehicles[
        REX_CONTENT_MAX_STARTER_OWNED
    ];
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

int RexContent_Load(
    RexContent* content,
    const char* path
);

#ifdef __cplusplus
}
#endif
