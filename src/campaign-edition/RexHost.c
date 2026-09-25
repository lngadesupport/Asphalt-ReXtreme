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
