#pragma once

#include "RexPresentationAdapterV2.h"

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

#ifdef __cplusplus
}
#endif
