#include "RexIntegrationShim.h"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <string.h>

typedef uint32_t (__cdecl *RexHostGetBoundaryAbiVersionFn)(void);
typedef int (__cdecl *RexHostStartV1Fn)(
    const char* content_path,
    const char* state_path,
    const RexGamePresentationPortV1* presentation_port
);
typedef int (__cdecl *RexHostIsStartedFn)(void);
typedef int (__cdecl *RexHostGarageEnterFn)(void);
typedef int (__cdecl *RexHostGarageSelectionChangedFn)(void);
typedef int (__cdecl *RexHostGarageMontarPressedFn)(void);

typedef struct RexShimState {
    HMODULE core_module;
    RexHostGetBoundaryAbiVersionFn get_boundary_abi_version;
    RexHostStartV1Fn start_v1;
    RexHostIsStartedFn is_core_started;
    RexHostGarageEnterFn garage_enter;
    RexHostGarageSelectionChangedFn garage_selection_changed;
    RexHostGarageMontarPressedFn garage_montar_pressed;
    uint32_t selected_vehicle_id;
    RexGarageSnapshotV1 snapshot;
    int has_snapshot;
    int last_action_result;
    int has_action_result;
    int started;
} RexShimState;

static RexShimState g_rex_shim;

static void RexShim_Reset(void) {
    HMODULE module = g_rex_shim.core_module;

    memset(&g_rex_shim, 0, sizeof(g_rex_shim));

    if (module != 0) {
        FreeLibrary(module);
    }
}

static uint32_t RexShim_ReadSelectedVehicleId(
    void* context
) {
    RexShimState* state = (RexShimState*)context;

    return state->selected_vehicle_id;
}

static void RexShim_PresentGarageSnapshot(
    void* context,
    const RexGarageSnapshotV1* snapshot
) {
    RexShimState* state = (RexShimState*)context;

    if (snapshot == 0 ||
        snapshot->abi_version != REX_BOUNDARY_ABI_VERSION ||
        snapshot->struct_size < (uint32_t)sizeof(*snapshot)) {
        return;
    }

    state->snapshot = *snapshot;
    state->has_snapshot = 1;
}

static void RexShim_PresentActionResult(
    void* context,
    int result
) {
    RexShimState* state = (RexShimState*)context;

    state->last_action_result = result;
    state->has_action_result = 1;
}

static FARPROC RexShim_FindProc(
    HMODULE module,
    const char* name
) {
    if (module == 0 || name == 0) {
        return 0;
    }

    return GetProcAddress(module, name);
}

uint32_t RexShim_GetAbiVersion(void) {
    return REX_SHIM_ABI_VERSION;
}

int RexShim_Start(
    const char* rex_core_path,
    const char* content_path,
    const char* state_path
) {
    RexGamePresentationPortV1 port = {0};

    if (g_rex_shim.started ||
        rex_core_path == 0 ||
        content_path == 0 ||
        state_path == 0) {
        return 0;
    }

    RexShim_Reset();

    g_rex_shim.core_module = LoadLibraryA(rex_core_path);
    if (g_rex_shim.core_module == 0) {
        RexShim_Reset();
        return 0;
    }

    g_rex_shim.get_boundary_abi_version =
        (RexHostGetBoundaryAbiVersionFn)RexShim_FindProc(
            g_rex_shim.core_module,
            "RexHost_GetBoundaryAbiVersion"
        );
    g_rex_shim.start_v1 =
        (RexHostStartV1Fn)RexShim_FindProc(
            g_rex_shim.core_module,
            "RexHost_StartV1"
        );
    g_rex_shim.is_core_started =
        (RexHostIsStartedFn)RexShim_FindProc(
            g_rex_shim.core_module,
            "RexHost_IsStarted"
        );
    g_rex_shim.garage_enter =
        (RexHostGarageEnterFn)RexShim_FindProc(
            g_rex_shim.core_module,
            "RexHost_GarageEnter"
        );
    g_rex_shim.garage_selection_changed =
        (RexHostGarageSelectionChangedFn)RexShim_FindProc(
            g_rex_shim.core_module,
            "RexHost_GarageSelectionChanged"
        );
    g_rex_shim.garage_montar_pressed =
        (RexHostGarageMontarPressedFn)RexShim_FindProc(
            g_rex_shim.core_module,
            "RexHost_GarageMontarPressed"
        );

    if (g_rex_shim.get_boundary_abi_version == 0 ||
        g_rex_shim.start_v1 == 0 ||
        g_rex_shim.is_core_started == 0 ||
        g_rex_shim.garage_enter == 0 ||
        g_rex_shim.garage_selection_changed == 0 ||
        g_rex_shim.garage_montar_pressed == 0 ||
        g_rex_shim.get_boundary_abi_version() !=
            REX_BOUNDARY_ABI_VERSION) {
        RexShim_Reset();
        return 0;
    }

    port.abi_version = REX_BOUNDARY_ABI_VERSION;
    port.struct_size = (uint32_t)sizeof(port);
    port.context = &g_rex_shim;
    port.read_selected_vehicle_id =
        RexShim_ReadSelectedVehicleId;
    port.present_garage_snapshot =
        RexShim_PresentGarageSnapshot;
    port.present_action_result =
        RexShim_PresentActionResult;

    if (!g_rex_shim.start_v1(
            content_path,
            state_path,
            &port) ||
        !g_rex_shim.is_core_started()) {
        RexShim_Reset();
        return 0;
    }

    g_rex_shim.started = 1;
    return 1;
}

int RexShim_IsStarted(void) {
    return g_rex_shim.started;
}

int RexShim_GarageEnter(
    uint32_t selected_vehicle_id
) {
    if (!g_rex_shim.started ||
        selected_vehicle_id == 0u) {
        return 0;
    }

    g_rex_shim.selected_vehicle_id = selected_vehicle_id;
    return g_rex_shim.garage_enter();
}

int RexShim_GarageSelectionChanged(
    uint32_t selected_vehicle_id
) {
    if (!g_rex_shim.started ||
        selected_vehicle_id == 0u) {
        return 0;
    }

    g_rex_shim.selected_vehicle_id = selected_vehicle_id;
    return g_rex_shim.garage_selection_changed();
}

int RexShim_GarageMontarPressed(void) {
    if (!g_rex_shim.started) {
        return -1;
    }

    return g_rex_shim.garage_montar_pressed();
}

int RexShim_CopyGarageSnapshot(
    RexGarageSnapshotV1* output
) {
    if (!g_rex_shim.started ||
        !g_rex_shim.has_snapshot ||
        output == 0) {
        return 0;
    }

    *output = g_rex_shim.snapshot;
    return 1;
}

int RexShim_GetLastActionResult(
    int* output
) {
    if (!g_rex_shim.started ||
        !g_rex_shim.has_action_result ||
        output == 0) {
        return 0;
    }

    *output = g_rex_shim.last_action_result;
    return 1;
}
