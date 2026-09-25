#pragma once

#include "RexBoundaryV1.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32)
#define REX_SHIM_API __declspec(dllexport)
#else
#define REX_SHIM_API
#endif

#define REX_SHIM_ABI_VERSION 1u

REX_SHIM_API uint32_t RexShim_GetAbiVersion(void);

REX_SHIM_API int RexShim_Start(
    const char* rex_core_path,
    const char* content_path,
    const char* state_path
);

REX_SHIM_API int RexShim_IsStarted(void);

REX_SHIM_API int RexShim_GarageEnter(
    uint32_t selected_vehicle_id
);

REX_SHIM_API int RexShim_GarageSelectionChanged(
    uint32_t selected_vehicle_id
);

REX_SHIM_API int RexShim_GarageMontarPressed(void);

REX_SHIM_API int RexShim_CopyGarageSnapshot(
    RexGarageSnapshotV1* output
);

REX_SHIM_API int RexShim_GetLastActionResult(
    int* output
);

#ifdef __cplusplus
}
#endif
