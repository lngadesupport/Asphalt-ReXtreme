#pragma once

#include "RexGaragePresenter.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct RexPresentationGaragePort {
    void* context;
    uint32_t (*read_selected_vehicle_id)(void* context);
    void (*present_garage)(
        void* context,
        const RexGarageViewModel* view_model,
        int focus_build
    );
    void (*present_action_result)(
        void* context,
        RexGaragePresenterResult result
    );
} RexPresentationGaragePort;

typedef struct RexPresentationAdapterV2 {
    RexGaragePresenter* presenter;
    RexPresentationGaragePort port;
} RexPresentationAdapterV2;

int RexPresentationAdapterV2_Init(
    RexPresentationAdapterV2* adapter,
    RexGaragePresenter* presenter,
    RexPresentationGaragePort port
);

int RexPresentationAdapterV2_OnEnter(
    RexPresentationAdapterV2* adapter
);

int RexPresentationAdapterV2_OnSelectionChanged(
    RexPresentationAdapterV2* adapter
);

RexGaragePresenterResult RexPresentationAdapterV2_OnMontarPressed(
    RexPresentationAdapterV2* adapter
);

#ifdef __cplusplus
}
#endif
