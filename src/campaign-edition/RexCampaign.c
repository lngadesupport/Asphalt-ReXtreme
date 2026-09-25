#include "RexCampaign.h"

#include <string.h>

int RexCampaign_Init(
    RexCampaign* campaign,
    const RexContent* content,
    RexState* state,
    RexGlobalSync* global_sync
) {
    if (campaign == 0 || content == 0 || state == 0 ||
        global_sync == 0 || !global_sync->initialized ||
        global_sync->state != state) {
        return 0;
    }

    campaign->content = content;
    campaign->state = state;
    campaign->global_sync = global_sync;
    return 1;
}

int RexCampaign_ReadVehicle(
    const RexCampaign* campaign,
    uint32_t vehicle_id,
    RexGarageViewModelInput* output
) {
    const RexContentVehicle* vehicle;

    if (campaign == 0 || campaign->content == 0 ||
        campaign->state == 0 || output == 0) {
        return 0;
    }

    vehicle = RexContent_FindVehicle(
        campaign->content,
        vehicle_id
    );
    if (vehicle == 0) {
        return 0;
    }

    memset(output, 0, sizeof(*output));
    output->selected_vehicle_id = vehicle_id;
    output->owned = RexState_IsOwned(
        campaign->state,
        vehicle_id
    );
    output->unlocked = vehicle->unlocked_by_default != 0;
    output->has_recipe = vehicle->has_recipe != 0;
    output->blueprint_cost = vehicle->blueprint_cost;
    output->blueprint_balance = RexState_GetBlueprintBalance(
        campaign->state,
        vehicle->blueprint_id
    );

    return 1;
}

RexCampaignActionResult RexCampaign_AcquireVehicle(
    RexCampaign* campaign,
    uint32_t vehicle_id
) {
    const RexContentVehicle* vehicle;
    RexState before;

    if (campaign == 0 || campaign->content == 0 ||
        campaign->state == 0 || campaign->global_sync == 0) {
        return REX_CAMPAIGN_ACTION_REJECTED;
    }

    vehicle = RexContent_FindVehicle(
        campaign->content,
        vehicle_id
    );

    if (vehicle == 0 ||
        !vehicle->unlocked_by_default ||
        !vehicle->has_recipe ||
        RexState_IsOwned(campaign->state, vehicle_id) ||
        RexState_GetBlueprintBalance(
            campaign->state,
            vehicle->blueprint_id
        ) < vehicle->blueprint_cost) {
        return REX_CAMPAIGN_ACTION_REJECTED;
    }

    before = *campaign->state;

    if (!RexState_SpendBlueprints(
            campaign->state,
            vehicle->blueprint_id,
            vehicle->blueprint_cost) ||
        !RexState_AddOwned(
            campaign->state,
            vehicle_id)) {
        *campaign->state = before;
        return REX_CAMPAIGN_ACTION_REJECTED;
    }

    RexState_SetGarageTutorialComplete(
        campaign->state,
        1
    );
    {
        uint32_t operation_id = 0u;

        if (RexGlobalSync_Commit(
                campaign->global_sync,
                REX_GLOBAL_SYNC_REASON_GARAGE,
                &operation_id) != REX_GLOBAL_SYNC_OK ||
            operation_id == 0u) {
            *campaign->state = before;
            return REX_CAMPAIGN_ACTION_IO_ERROR;
        }
    }

    return REX_CAMPAIGN_ACTION_OK;
}

int RexCampaign_IsGarageTutorialComplete(
    const RexCampaign* campaign
) {
    if (campaign == 0 || campaign->state == 0) {
        return 0;
    }

    return campaign->state->garage_tutorial_complete != 0;
}

int RexCampaign_CompleteGarageTutorial(
    RexCampaign* campaign
) {
    RexState before;

    if (campaign == 0 || campaign->state == 0 ||
        campaign->global_sync == 0) {
        return 0;
    }

    if (campaign->state->garage_tutorial_complete) {
        return 1;
    }

    before = *campaign->state;
    RexState_SetGarageTutorialComplete(
        campaign->state,
        1
    );
    {
        uint32_t operation_id = 0u;

        if (RexGlobalSync_Commit(
                campaign->global_sync,
                REX_GLOBAL_SYNC_REASON_GARAGE,
                &operation_id) != REX_GLOBAL_SYNC_OK ||
            operation_id == 0u) {
            *campaign->state = before;
            return 0;
        }
    }

    return 1;
}

static int RexCampaign_ApiReadVehicle(
    void* context,
    uint32_t vehicle_id,
    RexGarageViewModelInput* output
) {
    return RexCampaign_ReadVehicle(
        (const RexCampaign*)context,
        vehicle_id,
        output
    );
}

static RexCampaignActionResult RexCampaign_ApiAcquireVehicle(
    void* context,
    uint32_t vehicle_id
) {
    return RexCampaign_AcquireVehicle(
        (RexCampaign*)context,
        vehicle_id
    );
}

static int RexCampaign_ApiCompleteGarageTutorial(
    void* context
) {
    return RexCampaign_CompleteGarageTutorial(
        (RexCampaign*)context
    );
}

RexCampaignGarageApi RexCampaign_MakeGarageApi(
    RexCampaign* campaign
) {
    RexCampaignGarageApi api;

    api.context = campaign;
    api.read_vehicle = RexCampaign_ApiReadVehicle;
    api.acquire_vehicle = RexCampaign_ApiAcquireVehicle;
    api.complete_garage_tutorial =
        RexCampaign_ApiCompleteGarageTutorial;

    return api;
}
