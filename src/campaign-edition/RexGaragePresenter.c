#include "RexGaragePresenter.h"

static int RexGaragePresenter_Refresh(
    RexGaragePresenter* presenter,
    uint32_t selected_vehicle_id
) {
    RexGarageViewModelInput input = {0};

    if (!presenter->campaign.read_vehicle(
            presenter->campaign.context,
            selected_vehicle_id,
            &input)) {
        return 0;
    }

    RexGarageViewModel_Build(&input, &presenter->view_model);

    RexTutorialController_OnGarageEntered(
        &presenter->tutorial,
        presenter->view_model.build_enabled
    );

    return 1;
}

void RexGaragePresenter_Init(
    RexGaragePresenter* presenter,
    RexCampaignGarageApi campaign,
    int tutorial_completed
) {
    presenter->campaign = campaign;
    presenter->view_model.selected_vehicle_id = 0;
    presenter->view_model.owned = 0;
    presenter->view_model.unlocked = 0;
    presenter->view_model.build_enabled = 0;
    presenter->view_model.blueprint_balance = 0;
    presenter->view_model.blueprint_cost = 0;
    presenter->view_model.build_status = REX_GARAGE_BUILD_NO_SELECTION;

    RexTutorialController_Init(
        &presenter->tutorial,
        tutorial_completed
    );
}

int RexGaragePresenter_OnEnter(
    RexGaragePresenter* presenter,
    uint32_t selected_vehicle_id
) {
    return RexGaragePresenter_Refresh(
        presenter,
        selected_vehicle_id
    );
}

int RexGaragePresenter_OnCarSelected(
    RexGaragePresenter* presenter,
    uint32_t selected_vehicle_id
) {
    return RexGaragePresenter_Refresh(
        presenter,
        selected_vehicle_id
    );
}

RexGaragePresenterResult RexGaragePresenter_OnMontarPressed(
    RexGaragePresenter* presenter
) {
    const uint32_t vehicle_id = presenter->view_model.selected_vehicle_id;
    RexCampaignActionResult action;

    if (!presenter->view_model.build_enabled) {
        return REX_GARAGE_PRESENTER_NOT_BUILDABLE;
    }

    RexTutorialController_OnBuildPressed(&presenter->tutorial);

    action = presenter->campaign.acquire_vehicle(
        presenter->campaign.context,
        vehicle_id
    );

    if (action != REX_CAMPAIGN_ACTION_OK) {
        RexTutorialController_OnBuildResult(
            &presenter->tutorial,
            0
        );
        return REX_GARAGE_PRESENTER_CAMPAIGN_FAILED;
    }

    RexTutorialController_OnBuildResult(
        &presenter->tutorial,
        1
    );

    if (!RexGaragePresenter_Refresh(
            presenter,
            vehicle_id)) {
        return REX_GARAGE_PRESENTER_READ_FAILED;
    }

    return REX_GARAGE_PRESENTER_OK;
}

const RexGarageViewModel* RexGaragePresenter_GetViewModel(
    const RexGaragePresenter* presenter
) {
    return &presenter->view_model;
}

int RexGaragePresenter_ShouldFocusBuild(
    const RexGaragePresenter* presenter
) {
    return RexTutorialController_ShouldFocusBuild(
        &presenter->tutorial
    );
}

int RexGaragePresenter_IsTutorialComplete(
    const RexGaragePresenter* presenter
) {
    return RexTutorialController_IsComplete(
        &presenter->tutorial
    );
}
