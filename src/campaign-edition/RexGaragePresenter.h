#pragma once

#include "RexCampaign.h"
#include "RexGarageViewModel.h"
#include "RexTutorialController.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum RexGaragePresenterResult {
    REX_GARAGE_PRESENTER_OK = 0,
    REX_GARAGE_PRESENTER_NOT_BUILDABLE = 1,
    REX_GARAGE_PRESENTER_READ_FAILED = 2,
    REX_GARAGE_PRESENTER_CAMPAIGN_FAILED = 3
} RexGaragePresenterResult;

typedef struct RexGaragePresenter {
    RexCampaignGarageApi campaign;
    RexGarageViewModel view_model;
    RexTutorialController tutorial;
} RexGaragePresenter;

void RexGaragePresenter_Init(
    RexGaragePresenter* presenter,
    RexCampaignGarageApi campaign,
    int tutorial_completed
);

int RexGaragePresenter_OnEnter(
    RexGaragePresenter* presenter,
    uint32_t selected_vehicle_id
);

int RexGaragePresenter_OnCarSelected(
    RexGaragePresenter* presenter,
    uint32_t selected_vehicle_id
);

RexGaragePresenterResult RexGaragePresenter_OnMontarPressed(
    RexGaragePresenter* presenter
);

const RexGarageViewModel* RexGaragePresenter_GetViewModel(
    const RexGaragePresenter* presenter
);

int RexGaragePresenter_ShouldFocusBuild(
    const RexGaragePresenter* presenter
);

int RexGaragePresenter_IsTutorialComplete(
    const RexGaragePresenter* presenter
);

#ifdef __cplusplus
}
#endif
