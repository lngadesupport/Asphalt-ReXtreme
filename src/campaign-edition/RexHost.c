#include "RexHost.h"
#include "RexRuntime.h"

static RexRuntime g_rex_runtime;
static int g_rex_started = 0;

int RexHost_Start(
    const char* content_path,
    const char* state_path,
    const RexPresentationGaragePort* presentation_port
) {
    if (g_rex_started ||
        content_path == 0 ||
        state_path == 0 ||
        presentation_port == 0) {
        return 0;
    }

    if (!RexRuntime_Init(
            &g_rex_runtime,
            content_path,
            state_path,
            *presentation_port)) {
        return 0;
    }

    g_rex_started = 1;
    return 1;
}

int RexHost_IsStarted(void) {
    return g_rex_started;
}

int RexHost_GarageEnter(void) {
    if (!g_rex_started) {
        return 0;
    }

    return RexRuntime_OnGarageEnter(&g_rex_runtime);
}

int RexHost_GarageSelectionChanged(void) {
    if (!g_rex_started) {
        return 0;
    }

    return RexRuntime_OnGarageSelectionChanged(&g_rex_runtime);
}

int RexHost_GarageMontarPressed(void) {
    if (!g_rex_started) {
        return (int)REX_GARAGE_PRESENTER_READ_FAILED;
    }

    return (int)RexRuntime_OnGarageMontarPressed(
        &g_rex_runtime
    );
}

int RexHost_GaiaIsReady(void) {
    if (!g_rex_started) {
        return 0;
    }

    return RexGaia_IsReady(&g_rex_runtime.gaia);
}

int RexHost_GaiaIsNetworkRequired(void) {
    if (!g_rex_started) {
        return 1;
    }

    return RexGaia_IsNetworkRequired(&g_rex_runtime.gaia);
}

uint32_t RexHost_GlobalSyncPendingCount(void) {
    if (!g_rex_started) {
        return 0u;
    }

    return RexGlobalSync_GetPendingCount(
        &g_rex_runtime.global_sync
    );
}

int RexHost_GlobalSyncCommit(
    uint32_t reason,
    uint32_t* operation_id
) {
    if (!g_rex_started ||
        operation_id == 0 ||
        reason < (uint32_t)REX_GLOBAL_SYNC_REASON_PROFILE_BOOTSTRAP ||
        reason > (uint32_t)REX_GLOBAL_SYNC_REASON_CAREER) {
        return (int)REX_GLOBAL_SYNC_INVALID_ARGUMENT;
    }

    return (int)RexGlobalSync_Commit(
        &g_rex_runtime.global_sync,
        (RexGlobalSyncReason)reason,
        operation_id
    );
}
