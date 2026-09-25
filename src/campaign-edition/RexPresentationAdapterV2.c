#include "RexPresentationAdapterV2.h"

static void RexPresentationAdapterV2_Present(
    RexPresentationAdapterV2* adapter
) {
    adapter->port.present_garage(
        adapter->port.context,
        RexGaragePresenter_GetViewModel(adapter->presenter),
        RexGaragePresenter_ShouldFocusBuild(adapter->presenter)
    );
}

int RexPresentationAdapterV2_Init(
    RexPresentationAdapterV2* adapter,
    RexGaragePresenter* presenter,
    RexPresentationGaragePort port
) {
    if (adapter == 0 ||
        presenter == 0 ||
        port.read_selected_vehicle_id == 0 ||
        port.present_garage == 0 ||
        port.present_action_result == 0) {
        return 0;
    }

    adapter->presenter = presenter;
    adapter->port = port;
    return 1;
}

int RexPresentationAdapterV2_OnEnter(
    RexPresentationAdapterV2* adapter
) {
    uint32_t vehicle_id;

    if (adapter == 0 || adapter->presenter == 0) {
        return 0;
    }

    vehicle_id = adapter->port.read_selected_vehicle_id(
        adapter->port.context
    );

    if (!RexGaragePresenter_OnEnter(
            adapter->presenter,
            vehicle_id)) {
        return 0;
    }

    RexPresentationAdapterV2_Present(adapter);
    return 1;
}

int RexPresentationAdapterV2_OnSelectionChanged(
    RexPresentationAdapterV2* adapter
) {
    uint32_t vehicle_id;

    if (adapter == 0 || adapter->presenter == 0) {
        return 0;
    }

    vehicle_id = adapter->port.read_selected_vehicle_id(
        adapter->port.context
    );

    if (!RexGaragePresenter_OnCarSelected(
            adapter->presenter,
            vehicle_id)) {
        return 0;
    }

    RexPresentationAdapterV2_Present(adapter);
    return 1;
}

RexGaragePresenterResult RexPresentationAdapterV2_OnMontarPressed(
    RexPresentationAdapterV2* adapter
) {
    RexGaragePresenterResult result;

    if (adapter == 0 || adapter->presenter == 0) {
        return REX_GARAGE_PRESENTER_READ_FAILED;
    }

    result = RexGaragePresenter_OnMontarPressed(
        adapter->presenter
    );

    adapter->port.present_action_result(
        adapter->port.context,
        result
    );

    RexPresentationAdapterV2_Present(adapter);
    return result;
}
