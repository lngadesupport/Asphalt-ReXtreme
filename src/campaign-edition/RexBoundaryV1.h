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


#define REX_PLATFORM_DISPATCH_ABI_VERSION 1u

#define REX_PLATFORM_FLAG_PROFILE_READY         0x00000001u
#define REX_PLATFORM_FLAG_CLOUD_SYNC_ENABLED    0x00000002u
#define REX_PLATFORM_FLAG_NETWORK_REQUIRED      0x00000004u
#define REX_PLATFORM_FLAG_LOGIN_AUTHENTICATED   0x00000008u
#define REX_PLATFORM_FLAG_LICENSE_ACTIVE        0x00000010u
#define REX_PLATFORM_FLAG_IAP_ENABLED           0x00000020u
#define REX_PLATFORM_FLAG_ADS_ENABLED           0x00000040u
#define REX_PLATFORM_FLAG_SOCIAL_ENABLED        0x00000080u
#define REX_PLATFORM_FLAG_MATCHMAKING_ENABLED   0x00000100u
#define REX_PLATFORM_FLAG_ONLINE_EVENTS_ENABLED 0x00000200u
#define REX_PLATFORM_FLAG_UPDATE_REQUIRED       0x00000400u

typedef enum RexPlatformOpcodeV1 {
    REX_PLATFORM_OP_GET_CAPABILITIES = 1,
    REX_PLATFORM_OP_GAIA_STATUS = 2,
    REX_PLATFORM_OP_GLOBAL_SYNC_COMMIT = 3,
    REX_PLATFORM_OP_PROFILE_STATUS = 4,
    REX_PLATFORM_OP_CONNECTIVITY_STATUS = 5,
    REX_PLATFORM_OP_LOGIN_STATUS = 6,
    REX_PLATFORM_OP_LICENSE_STATUS = 7,
    REX_PLATFORM_OP_REMOTE_CONFIG_BOOL = 8,
    REX_PLATFORM_OP_MAILBOX_COUNT = 9,
    REX_PLATFORM_OP_LEADERBOARD_SUBMIT = 10,
    REX_PLATFORM_OP_LEADERBOARD_GET = 11,
    REX_PLATFORM_OP_ECONOMY_SET = 12,
    REX_PLATFORM_OP_ECONOMY_CREDIT = 13,
    REX_PLATFORM_OP_ECONOMY_DEBIT = 14,
    REX_PLATFORM_OP_ECONOMY_GET = 15,
    REX_PLATFORM_OP_IAP_PURCHASE = 16,
    REX_PLATFORM_OP_ADS_REQUEST = 17,
    REX_PLATFORM_OP_SOCIAL_LOGIN = 18,
    REX_PLATFORM_OP_MATCHMAKING_START = 19,
    REX_PLATFORM_OP_EVENTS_REFRESH = 20,
    REX_PLATFORM_OP_INVENTORY_SET = 21,
    REX_PLATFORM_OP_INVENTORY_ADD = 22,
    REX_PLATFORM_OP_INVENTORY_GET = 23,
    REX_PLATFORM_OP_PROGRESSION_SET = 24,
    REX_PLATFORM_OP_PROGRESSION_GET = 25,
    REX_PLATFORM_OP_VERSION_STATUS = 26
} RexPlatformOpcodeV1;

typedef struct RexPlatformRequestV1 {
    uint32_t abi_version;
    uint32_t struct_size;
    uint32_t opcode;
    int32_t status;
    uint32_t id;
    uint32_t aux_u32;
    uint64_t value;
    uint64_t result;
    char text[64];
} RexPlatformRequestV1;

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
