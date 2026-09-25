#include "RexGarageViewModel.h"

void RexGarageViewModel_Build(
    const RexGarageViewModelInput* input,
    RexGarageViewModel* output
) {
    output->selected_vehicle_id = input->selected_vehicle_id;
    output->owned = input->owned != 0;
    output->unlocked = input->unlocked != 0;
    output->build_enabled = 0;
    output->blueprint_balance = input->blueprint_balance;
    output->blueprint_cost = input->blueprint_cost;

    if (input->selected_vehicle_id == 0) {
        output->build_status = REX_GARAGE_BUILD_NO_SELECTION;
        return;
    }

    if (input->owned) {
        output->build_status = REX_GARAGE_BUILD_OWNED;
        return;
    }

    if (!input->unlocked) {
        output->build_status = REX_GARAGE_BUILD_LOCKED;
        return;
    }

    if (!input->has_recipe) {
        output->build_status = REX_GARAGE_BUILD_UNAVAILABLE;
        return;
    }

    if (input->blueprint_balance < input->blueprint_cost) {
        output->build_status = REX_GARAGE_BUILD_NEEDS_BLUEPRINTS;
        return;
    }

    output->build_enabled = 1;
    output->build_status = REX_GARAGE_BUILD_READY;
}
