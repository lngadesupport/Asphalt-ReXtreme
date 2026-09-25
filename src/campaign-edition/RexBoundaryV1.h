#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32)
#define REX_BOUNDARY_API __declspec(dllexport)
#else
#define REX_BOUNDARY_API
#endif

#define REX_BOUNDARY_ABI_VERSION 1u

typedef struct RexGarageSnapshotV1 {
    uint32_t abi_version;
    uint32_t struct_size;
    uint32_t selected_vehicle_id;
    uint32_t blueprint_balance;
    uint32_t blueprint_cost;
    int32_t owned;
    int32_t unlocked;
    int32_t montar_enabled;
    int32_t build_status;
    int32_t focus_montar;
} RexGarageSnapshotV1;

typedef struct RexGamePresentationPortV1 {
    uint32_t abi_version;
    uint32_t struct_size;
    void* context;
    uint32_t (*read_selected_vehicle_id)(void* context);
    void (*present_garage_snapshot)(
        void* context,
        const RexGarageSnapshotV1* snapshot
    );
    void (*present_action_result)(
        void* context,
        int result
    );
} RexGamePresentationPortV1;

REX_BOUNDARY_API uint32_t RexHost_GetBoundaryAbiVersion(void);

REX_BOUNDARY_API int RexHost_StartV1(
    const char* content_path,
    const char* state_path,
    const RexGamePresentationPortV1* presentation_port
);

#ifdef __cplusplus
}
#endif
