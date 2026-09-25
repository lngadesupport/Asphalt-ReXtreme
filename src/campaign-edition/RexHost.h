#pragma once

#include "RexPresentationAdapterV2.h"
#include "RexBoundaryV1.h"
#include "RexGlobalSync.h"

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32)
#define REX_HOST_API __declspec(dllexport)
#else
#define REX_HOST_API
#endif

REX_HOST_API int RexHost_Start(
    const char* content_path,
    const char* state_path,
    const RexPresentationGaragePort* presentation_port
);

REX_HOST_API int RexHost_IsStarted(void);

REX_HOST_API int RexHost_GarageEnter(void);

REX_HOST_API int RexHost_GarageSelectionChanged(void);

REX_HOST_API int RexHost_GarageMontarPressed(void);

REX_HOST_API int RexHost_GaiaIsReady(void);

REX_HOST_API int RexHost_GaiaIsNetworkRequired(void);

REX_HOST_API uint32_t RexHost_GlobalSyncPendingCount(void);

REX_HOST_API int RexHost_GlobalSyncCommit(
    uint32_t reason,
    uint32_t* operation_id
);

REX_HOST_API int RexHost_PlatformDispatchV1(
    RexPlatformRequestV1* request
);

#ifdef __cplusplus
}
#endif
