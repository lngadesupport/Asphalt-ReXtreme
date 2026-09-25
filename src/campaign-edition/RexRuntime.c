#include "RexRuntime.h"

#include <string.h>

int RexRuntime_Init(
    RexRuntime* runtime,
    const char* content_path,
    const char* state_path,
    RexPresentationGaragePort presentation_port
) {
    if (runtime == 0 || content_path == 0 || state_path == 0) {
        return 0;
    }

    memset(runtime, 0, sizeof(*runtime));

    if (!RexContent_Load(
            &runtime->content,
            content_path)) {
        return 0;
    }

    if (strcpy_s(
            runtime->state_path,
            sizeof(runtime->state_path),
            state_path) != 0) {
        return 0;
    }

    RexState_Init(&runtime->state);

    if (!RexState_Load(
            &runtime->state,
            runtime->state_path)) {
        RexState_Init(&runtime->state);

        if (!RexState_Save(
                &runtime->state,
                runtime->state_path)) {
            return 0;
        }
    }

    if (!RexCampaign_Init(
            &runtime->campaign,
            &runtime->content,
            &runtime->state,
            runtime->state_path)) {
        return 0;
    }

    RexGaragePresenter_Init(
        &runtime->garage_presenter,
        RexCampaign_MakeGarageApi(&runtime->campaign),
        RexCampaign_IsGarageTutorialComplete(&runtime->campaign)
    );

    if (!RexPresentationAdapterV2_Init(
            &runtime->presentation_adapter,
            &runtime->garage_presenter,
            presentation_port)) {
        return 0;
    }

    runtime->initialized = 1;
    return 1;
}

int RexRuntime_OnGarageEnter(
    RexRuntime* runtime
) {
    if (runtime == 0 || !runtime->initialized) {
        return 0;
    }

    return RexPresentationAdapterV2_OnEnter(
        &runtime->presentation_adapter
    );
}

int RexRuntime_OnGarageSelectionChanged(
    RexRuntime* runtime
) {
    if (runtime == 0 || !runtime->initialized) {
        return 0;
    }

    return RexPresentationAdapterV2_OnSelectionChanged(
        &runtime->presentation_adapter
    );
}

RexGaragePresenterResult RexRuntime_OnGarageMontarPressed(
    RexRuntime* runtime
) {
    if (runtime == 0 || !runtime->initialized) {
        return REX_GARAGE_PRESENTER_READ_FAILED;
    }

    return RexPresentationAdapterV2_OnMontarPressed(
        &runtime->presentation_adapter
    );
}
