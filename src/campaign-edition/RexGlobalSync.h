#pragma once

#include <stdint.h>

#include "RexState.h"

#ifdef __cplusplus
extern "C" {
#endif

#define REX_GLOBAL_SYNC_PATH_MAX 512u

typedef enum RexGlobalSyncResult {
    REX_GLOBAL_SYNC_OK = 0,
    REX_GLOBAL_SYNC_INVALID_ARGUMENT = 1,
    REX_GLOBAL_SYNC_SAVE_FAILED = 2
} RexGlobalSyncResult;

typedef enum RexGlobalSyncReason {
    REX_GLOBAL_SYNC_REASON_PROFILE_BOOTSTRAP = 1,
    REX_GLOBAL_SYNC_REASON_STATE_MUTATION = 2,
    REX_GLOBAL_SYNC_REASON_GARAGE = 3,
    REX_GLOBAL_SYNC_REASON_CAREER = 4
} RexGlobalSyncReason;

typedef void (*RexGlobalSyncCompletion)(
    void* context,
    uint32_t operation_id,
    RexGlobalSyncResult result,
    uint64_t revision
);

typedef struct RexGlobalSync {
    RexState* state;
    char state_path[REX_GLOBAL_SYNC_PATH_MAX];
    RexGlobalSyncCompletion completion;
    void* completion_context;
    uint32_t next_operation_id;
    uint32_t pending_count;
    int initialized;
} RexGlobalSync;

int RexGlobalSync_Init(
    RexGlobalSync* sync,
    RexState* state,
    const char* state_path,
    RexGlobalSyncCompletion completion,
    void* completion_context
);

int RexGlobalSync_IsNetworkRequired(
    const RexGlobalSync* sync
);

uint32_t RexGlobalSync_GetPendingCount(
    const RexGlobalSync* sync
);

RexGlobalSyncResult RexGlobalSync_Commit(
    RexGlobalSync* sync,
    RexGlobalSyncReason reason,
    uint32_t* operation_id
);

#ifdef __cplusplus
}
#endif
