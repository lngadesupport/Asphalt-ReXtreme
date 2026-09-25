#include "RexBoundaryV1.h"

#include "RexHost.h"

static RexGamePresentationPortV1 g_boundary_port;

static uint32_t RexBoundaryV1_ReadSelectedVehicle(
    void* context
) {
    RexGamePresentationPortV1* port =
        (RexGamePresentationPortV1*)context;

    return port->read_selected_vehicle_id(
        port->context
    );
}

static void RexBoundaryV1_PresentGarage(
    void* context,
    const RexGarageViewModel* view_model,
    int focus_build
) {
    RexGamePresentationPortV1* port =
        (RexGamePresentationPortV1*)context;
    RexGarageSnapshotV1 snapshot = {0};

    snapshot.abi_version = REX_BOUNDARY_ABI_VERSION;
    snapshot.struct_size = (uint32_t)sizeof(snapshot);
    snapshot.selected_vehicle_id =
        view_model->selected_vehicle_id;
    snapshot.blueprint_balance =
        view_model->blueprint_balance;
    snapshot.blueprint_cost =
        view_model->blueprint_cost;
    snapshot.owned = view_model->owned;
    snapshot.unlocked = view_model->unlocked;
    snapshot.montar_enabled =
        view_model->build_enabled;
    snapshot.build_status =
        (int32_t)view_model->build_status;
    snapshot.focus_montar =
        focus_build != 0;

    port->present_garage_snapshot(
        port->context,
        &snapshot
    );
}

static void RexBoundaryV1_PresentActionResult(
    void* context,
    RexGaragePresenterResult result
) {
    RexGamePresentationPortV1* port =
        (RexGamePresentationPortV1*)context;

    port->present_action_result(
        port->context,
        (int)result
    );
}

uint32_t RexHost_GetBoundaryAbiVersion(void) {
    return REX_BOUNDARY_ABI_VERSION;
}

int RexHost_StartV1(
    const char* content_path,
    const char* state_path,
    const RexGamePresentationPortV1* presentation_port
) {
    RexPresentationGaragePort internal_port = {0};

    if (content_path == 0 ||
        state_path == 0 ||
        presentation_port == 0 ||
        presentation_port->abi_version !=
            REX_BOUNDARY_ABI_VERSION ||
        presentation_port->struct_size <
            (uint32_t)sizeof(*presentation_port) ||
        presentation_port->read_selected_vehicle_id == 0 ||
        presentation_port->present_garage_snapshot == 0 ||
        presentation_port->present_action_result == 0) {
        return 0;
    }

    g_boundary_port = *presentation_port;

    internal_port.context = &g_boundary_port;
    internal_port.read_selected_vehicle_id =
        RexBoundaryV1_ReadSelectedVehicle;
    internal_port.present_garage =
        RexBoundaryV1_PresentGarage;
    internal_port.present_action_result =
        RexBoundaryV1_PresentActionResult;

    return RexHost_Start(
        content_path,
        state_path,
        &internal_port
    );
}
