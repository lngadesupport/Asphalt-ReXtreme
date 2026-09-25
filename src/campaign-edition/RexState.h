#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REX_STATE_VERSION 1u
#define REX_STATE_MAX_OWNED_VEHICLES 128u
#define REX_STATE_MAX_BLUEPRINTS 256u

typedef struct RexStateBlueprintBalance {
    uint32_t blueprint_id;
    uint32_t amount;
} RexStateBlueprintBalance;

typedef struct RexState {
    uint32_t version;
    uint64_t revision;
    uint32_t owned_count;
    uint32_t owned_vehicles[REX_STATE_MAX_OWNED_VEHICLES];
    uint32_t blueprint_count;
    RexStateBlueprintBalance blueprints[REX_STATE_MAX_BLUEPRINTS];
    int garage_tutorial_complete;
} RexState;

void RexState_Init(RexState* state);

int RexState_IsOwned(
    const RexState* state,
    uint32_t vehicle_id
);

int RexState_AddOwned(
    RexState* state,
    uint32_t vehicle_id
);

uint32_t RexState_GetBlueprintBalance(
    const RexState* state,
    uint32_t blueprint_id
);

int RexState_SetBlueprintBalance(
    RexState* state,
    uint32_t blueprint_id,
    uint32_t amount
);

int RexState_SpendBlueprints(
    RexState* state,
    uint32_t blueprint_id,
    uint32_t amount
);

void RexState_SetGarageTutorialComplete(
    RexState* state,
    int complete
);

int RexState_Save(
    const RexState* state,
    const char* path
);

int RexState_Load(
    RexState* state,
    const char* path
);

#ifdef __cplusplus
}
#endif
