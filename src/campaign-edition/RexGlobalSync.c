#include "RexGlobalSync.h"

#include <string.h>

int RexGlobalSync_Init(
    RexGlobalSync* sync,
    RexState* state,
    const char* state_path,
    RexGlobalSyncCompletion completion,
    void* completion_context
) {
    if (sync == 0 ||
        state == 0 ||
        state_path == 0 ||
        state_path[0] == '\0') {
        return 0;
    }

    memset(sync, 0, sizeof(*sync));

    if (strcpy_s(
            sync->state_path,
            sizeof(sync->state_path),
            state_path) != 0) {
        return 0;
    }

    sync->state = state;
    sync->completion = completion;
    sync->completion_context = completion_context;
    sync->next_operation_id = 1u;
    sync->initialized = 1;
    return 1;
}

int RexGlobalSync_IsNetworkRequired(
    const RexGlobalSync* sync
) {
    (void)sync;
    return 0;
}

uint32_t RexGlobalSync_GetPendingCount(
    const RexGlobalSync* sync
) {
    if (sync == 0 || !sync->initialized) {
        return 0u;
    }

    return sync->pending_count;
}

RexGlobalSyncResult RexGlobalSync_Commit(
    RexGlobalSync* sync,
    RexGlobalSyncReason reason,
    uint32_t* operation_id
) {
    uint32_t id;
    uint64_t previous_revision;
    RexGlobalSyncResult result;

    if (sync == 0 ||
        !sync->initialized ||
        sync->state == 0 ||
        reason == 0 ||
        operation_id == 0) {
        return REX_GLOBAL_SYNC_INVALID_ARGUMENT;
    }

    id = sync->next_operation_id;
    sync->next_operation_id += 1u;
    sync->pending_count += 1u;
    *operation_id = id;

    previous_revision = sync->state->revision;
    sync->state->revision = previous_revision + 1u;

    if (RexState_Save(
            sync->state,
            sync->state_path)) {
        result = REX_GLOBAL_SYNC_OK;
    } else {
        sync->state->revision = previous_revision;
        result = REX_GLOBAL_SYNC_SAVE_FAILED;
    }

    sync->pending_count -= 1u;

    if (sync->completion != 0) {
        sync->completion(
            sync->completion_context,
            id,
            result,
            sync->state->revision
        );
    }

    return result;
}
