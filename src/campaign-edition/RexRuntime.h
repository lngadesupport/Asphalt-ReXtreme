#pragma once

#include "RexCampaign.h"
#include "RexContent.h"
#include "RexGaragePresenter.h"
#include "RexGaia.h"
#include "RexGlobalSync.h"
#include "RexPlatformServices.h"
#include "RexPresentationAdapterV2.h"
#include "RexState.h"

#ifdef __cplusplus
extern "C" {
#endif

#define REX_RUNTIME_PATH_MAX 512u

typedef struct RexRuntime {
    RexContent content;
    RexState state;
    RexGaia gaia;
    RexPlatformServices platform_services;
    RexGlobalSync global_sync;
    RexCampaign campaign;
    RexGaragePresenter garage_presenter;
    RexPresentationAdapterV2 presentation_adapter;
    char state_path[REX_RUNTIME_PATH_MAX];
    int initialized;
} RexRuntime;

int RexRuntime_Init(
    RexRuntime* runtime,
    const char* content_path,
    const char* state_path,
    RexPresentationGaragePort presentation_port
);

int RexRuntime_OnGarageEnter(
    RexRuntime* runtime
);

int RexRuntime_OnGarageSelectionChanged(
    RexRuntime* runtime
);

RexGaragePresenterResult RexRuntime_OnGarageMontarPressed(
    RexRuntime* runtime
);

#ifdef __cplusplus
}
#endif
