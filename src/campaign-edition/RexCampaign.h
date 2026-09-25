#pragma once

#include "RexContent.h"
#include "RexGarageViewModel.h"
#include "RexGlobalSync.h"
#include "RexState.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum RexCampaignActionResult {
    REX_CAMPAIGN_ACTION_OK = 0,
    REX_CAMPAIGN_ACTION_REJECTED = 1,
    REX_CAMPAIGN_ACTION_IO_ERROR = 2
} RexCampaignActionResult;

typedef struct RexCampaignGarageApi {
    void* context;
    int (*read_vehicle)(
        void* context,
        uint32_t vehicle_id,
        RexGarageViewModelInput* output
    );
    RexCampaignActionResult (*acquire_vehicle)(
        void* context,
        uint32_t vehicle_id
    );
    int (*complete_garage_tutorial)(
        void* context
    );
} RexCampaignGarageApi;

typedef struct RexCampaign {
    const RexContent* content;
    RexState* state;
    RexGlobalSync* global_sync;
} RexCampaign;

int RexCampaign_Init(
    RexCampaign* campaign,
    const RexContent* content,
    RexState* state,
    RexGlobalSync* global_sync
);

int RexCampaign_ReadVehicle(
    const RexCampaign* campaign,
    uint32_t vehicle_id,
    RexGarageViewModelInput* output
);

RexCampaignActionResult RexCampaign_AcquireVehicle(
    RexCampaign* campaign,
    uint32_t vehicle_id
);

int RexCampaign_IsGarageTutorialComplete(
    const RexCampaign* campaign
);

int RexCampaign_CompleteGarageTutorial(
    RexCampaign* campaign
);

RexCampaignGarageApi RexCampaign_MakeGarageApi(
    RexCampaign* campaign
);

#ifdef __cplusplus
}
#endif
