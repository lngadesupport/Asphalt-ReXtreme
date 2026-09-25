#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <appmodel.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "RexIgpProxy.h"
#include "RexIntegrationShim.h"

#define REX_GARAGE_SELECTED_OFFSET 0x2D4u
#define REX_SELECTED_VEHICLE_ID_OFFSET 0xC0u
#define REX_PATH_CAPACITY 1024u

typedef uint32_t (__cdecl *RexShimGetAbiVersionFn)(void);
typedef int (__cdecl *RexShimStartFn)(
    const char* rex_core_path,
    const char* content_path,
    const char* state_path
);
typedef int (__cdecl *RexShimIsStartedFn)(void);
typedef int (__cdecl *RexShimGarageEnterFn)(uint32_t);
typedef int (__cdecl *RexShimGarageSelectionChangedFn)(uint32_t);
typedef int (__cdecl *RexShimGarageMontarPressedFn)(void);
typedef int (__cdecl *RexShimCopyGarageSnapshotFn)(
    RexGarageSnapshotV1*
);
typedef int (__cdecl *RexShimPlatformDispatchV1Fn)(
    RexPlatformRequestV1*
);

typedef struct RexProxyRuntime {
    HMODULE module;
    RexShimGetAbiVersionFn get_abi_version;
    RexShimStartFn start;
    RexShimIsStartedFn is_started;
    RexShimGarageEnterFn garage_enter;
    RexShimGarageSelectionChangedFn selection_changed;
    RexShimGarageMontarPressedFn montar_pressed;
    RexShimCopyGarageSnapshotFn copy_snapshot;
    RexShimPlatformDispatchV1Fn platform_dispatch_v1;
    int ready;
} RexProxyRuntime;

static HMODULE g_proxy_module;
static int g_proxy_instance;
static RexProxyRuntime g_runtime;

static int RexProxy_GetModuleDirectory(
    char* output,
    size_t capacity
) {
    DWORD length;
    char* slash;

    if (output == 0 || capacity < 2u || g_proxy_module == 0) {
        return 0;
    }

    length = GetModuleFileNameA(
        g_proxy_module,
        output,
        (DWORD)capacity
    );
    if (length == 0u || length >= capacity) {
        return 0;
    }

    slash = strrchr(output, '\\');
    if (slash == 0) {
        slash = strrchr(output, '/');
    }
    if (slash == 0) {
        return 0;
    }

    *slash = '\0';
    return 1;
}

static int RexProxy_JoinPath(
    char* output,
    size_t capacity,
    const char* directory,
    const char* name
) {
    int written;

    if (output == 0 || directory == 0 || name == 0) {
        return 0;
    }

    written = sprintf_s(
        output,
        capacity,
        "%s\\%s",
        directory,
        name
    );

    return written > 0 && (size_t)written < capacity;
}

static int RexProxy_GetStatePath(
    char* output,
    size_t capacity,
    const char* module_directory
) {
    char local_app_data[REX_PATH_CAPACITY];
    wchar_t family_w[128];
    char family_a[256];
    UINT32 family_length =
        (UINT32)(sizeof(family_w) / sizeof(family_w[0]));
    LONG package_result;
    DWORD local_length;
    int converted;
    int written;

    package_result = GetCurrentPackageFamilyName(
        &family_length,
        family_w
    );

    local_length = GetEnvironmentVariableA(
        "LOCALAPPDATA",
        local_app_data,
        (DWORD)sizeof(local_app_data)
    );

    if (package_result == ERROR_SUCCESS &&
        local_length > 0u &&
        local_length < sizeof(local_app_data)) {
        converted = WideCharToMultiByte(
            CP_ACP,
            0,
            family_w,
            -1,
            family_a,
            (int)sizeof(family_a),
            0,
            0
        );

        if (converted > 0) {
            if (strstr(local_app_data, family_a) != 0 &&
                strstr(local_app_data, "LocalState") != 0) {
                written = sprintf_s(
                    output,
                    capacity,
                    "%s\\CampaignStateV1.dat",
                    local_app_data
                );
            } else {
                written = sprintf_s(
                    output,
                    capacity,
                    "%s\\Packages\\%s\\LocalState\\CampaignStateV1.dat",
                    local_app_data,
                    family_a
                );
            }

            if (written > 0 && (size_t)written < capacity) {
                return 1;
            }
        }
    }

    return RexProxy_JoinPath(
        output,
        capacity,
        module_directory,
        "CampaignStateV1.dat"
    );
}

static FARPROC RexProxy_Find(
    HMODULE module,
    const char* name
) {
    if (module == 0 || name == 0) {
        return 0;
    }
    return GetProcAddress(module, name);
}

static void RexProxy_ResetRuntime(void) {
    HMODULE module = g_runtime.module;

    memset(&g_runtime, 0, sizeof(g_runtime));

    if (module != 0) {
        FreeLibrary(module);
    }
}

static int RexProxy_EnsureRuntime(void) {
    char directory[REX_PATH_CAPACITY];
    char shim_path[REX_PATH_CAPACITY];
    char core_path[REX_PATH_CAPACITY];
    char content_path[REX_PATH_CAPACITY];
    char state_path[REX_PATH_CAPACITY];

    if (g_runtime.ready) {
        return 1;
    }

    RexProxy_ResetRuntime();

    if (!RexProxy_GetModuleDirectory(
            directory,
            sizeof(directory)) ||
        !RexProxy_JoinPath(
            shim_path,
            sizeof(shim_path),
            directory,
            "RexGameShim.dll") ||
        !RexProxy_JoinPath(
            core_path,
            sizeof(core_path),
            directory,
            "RexCore.dll") ||
        !RexProxy_JoinPath(
            content_path,
            sizeof(content_path),
            directory,
            "CampaignContentV2.dat") ||
        !RexProxy_GetStatePath(
            state_path,
            sizeof(state_path),
            directory)) {
        return 0;
    }

    g_runtime.module = LoadLibraryA(shim_path);
    if (g_runtime.module == 0) {
        RexProxy_ResetRuntime();
        return 0;
    }

    g_runtime.get_abi_version =
        (RexShimGetAbiVersionFn)RexProxy_Find(
            g_runtime.module,
            "RexShim_GetAbiVersion"
        );
    g_runtime.start =
        (RexShimStartFn)RexProxy_Find(
            g_runtime.module,
            "RexShim_Start"
        );
    g_runtime.is_started =
        (RexShimIsStartedFn)RexProxy_Find(
            g_runtime.module,
            "RexShim_IsStarted"
        );
    g_runtime.garage_enter =
        (RexShimGarageEnterFn)RexProxy_Find(
            g_runtime.module,
            "RexShim_GarageEnter"
        );
    g_runtime.selection_changed =
        (RexShimGarageSelectionChangedFn)RexProxy_Find(
            g_runtime.module,
            "RexShim_GarageSelectionChanged"
        );
    g_runtime.montar_pressed =
        (RexShimGarageMontarPressedFn)RexProxy_Find(
            g_runtime.module,
            "RexShim_GarageMontarPressed"
        );
    g_runtime.copy_snapshot =
        (RexShimCopyGarageSnapshotFn)RexProxy_Find(
            g_runtime.module,
            "RexShim_CopyGarageSnapshot"
        );
    g_runtime.platform_dispatch_v1 =
        (RexShimPlatformDispatchV1Fn)RexProxy_Find(
            g_runtime.module,
            "RexShim_PlatformDispatchV1"
        );

    if (g_runtime.get_abi_version == 0 ||
        g_runtime.start == 0 ||
        g_runtime.is_started == 0 ||
        g_runtime.garage_enter == 0 ||
        g_runtime.selection_changed == 0 ||
        g_runtime.montar_pressed == 0 ||
        g_runtime.copy_snapshot == 0 ||
        g_runtime.platform_dispatch_v1 == 0 ||
        g_runtime.get_abi_version() != REX_SHIM_ABI_VERSION) {
        RexProxy_ResetRuntime();
        return 0;
    }

    if (!g_runtime.is_started()) {
        if (!g_runtime.start(
                core_path,
                content_path,
                state_path)) {
            RexProxy_ResetRuntime();
            return 0;
        }
    }

    if (!g_runtime.is_started()) {
        RexProxy_ResetRuntime();
        return 0;
    }

    g_runtime.ready = 1;
    return 1;
}

static int RexProxy_ReadSelectedVehicle(
    void* garage,
    uint32_t* vehicle_id
) {
    unsigned char* garage_bytes;
    void* selected = 0;
    unsigned char* selected_bytes;

    if (garage == 0 || vehicle_id == 0) {
        return 0;
    }

    garage_bytes = (unsigned char*)garage;
    memcpy(
        &selected,
        garage_bytes + REX_GARAGE_SELECTED_OFFSET,
        sizeof(selected)
    );
    if (selected == 0) {
        return 0;
    }

    selected_bytes = (unsigned char*)selected;
    memcpy(
        vehicle_id,
        selected_bytes + REX_SELECTED_VEHICLE_ID_OFFSET,
        sizeof(*vehicle_id)
    );

    return *vehicle_id != 0u;
}

BOOL WINAPI DllMain(
    HINSTANCE module,
    DWORD reason,
    LPVOID reserved
) {
    (void)reserved;

    if (reason == DLL_PROCESS_ATTACH) {
        g_proxy_module = module;
        DisableThreadLibraryCalls(module);
    }

    return TRUE;
}

void __fastcall RexIGP_AddIGPComponent(
    void* self,
    void* ignored_edx,
    const char* component
) {
    (void)self;
    (void)ignored_edx;
    (void)component;
}

void __cdecl RexIGP_DestroyIGP(void) {
}

void* __cdecl RexIGP_GetInstance(void) {
    return &g_proxy_instance;
}

int __fastcall RexIGP_HttpPostLink(
    void* self,
    void* ignored_edx,
    const char* link
) {
    uintptr_t selector = (uintptr_t)link;
    uint32_t vehicle_id;
    RexGarageSnapshotV1 snapshot;

    (void)ignored_edx;

    if (selector == (uintptr_t)REX_IGP_GATE_PLATFORM_DISPATCH) {
        RexPlatformRequestV1* request =
            (RexPlatformRequestV1*)self;

        if (request == 0 ||
            !RexProxy_EnsureRuntime() ||
            !g_runtime.platform_dispatch_v1(request)) {
            return -1;
        }

        return request->status;
    }

    if (selector == (uintptr_t)REX_IGP_GATE_MONTAR) {
        if (!RexProxy_ReadSelectedVehicle(
                self,
                &vehicle_id) ||
            !RexProxy_EnsureRuntime() ||
            !g_runtime.garage_enter(vehicle_id)) {
            return -1;
        }

        return g_runtime.montar_pressed();
    }

    if (selector == (uintptr_t)REX_IGP_GATE_OWNED) {
        vehicle_id = (uint32_t)(uintptr_t)self;

        if (vehicle_id == 0u ||
            !RexProxy_EnsureRuntime() ||
            !g_runtime.selection_changed(vehicle_id)) {
            return 0;
        }

        memset(&snapshot, 0, sizeof(snapshot));
        if (!g_runtime.copy_snapshot(&snapshot) ||
            snapshot.abi_version != REX_BOUNDARY_ABI_VERSION ||
            snapshot.selected_vehicle_id != vehicle_id) {
            return 0;
        }

        return snapshot.owned != 0;
    }

    return 0;
}

void __cdecl RexIGP_Init(const void* params) {
    (void)params;
    (void)RexProxy_EnsureRuntime();
}

void __cdecl RexIGP_InitBridgeCallbacks(void) {
}

void __cdecl RexIGP_InitBridgeClass(void* panel) {
    (void)panel;
}

int __cdecl RexIGP_IsOnScreenFreemium(void) {
    return 0;
}

void __fastcall RexIGP_PauseIGP(
    void* self,
    void* ignored_edx
) {
    (void)self;
    (void)ignored_edx;
}

void __fastcall RexIGP_ResumeIGP(
    void* self,
    void* ignored_edx
) {
    (void)self;
    (void)ignored_edx;
}

void __cdecl RexIGP_SetGender(const char* value) {
    (void)value;
}

void __fastcall RexIGP_SetIGPLanguage(
    void* self,
    void* ignored_edx,
    const char* value
) {
    (void)self;
    (void)ignored_edx;
    (void)value;
}

void __cdecl RexIGP_SetUserAge(const char* value) {
    (void)value;
}

void __fastcall RexIGP_ShowIGP(
    void* self,
    void* ignored_edx,
    int show
) {
    (void)self;
    (void)ignored_edx;
    (void)show;
}
