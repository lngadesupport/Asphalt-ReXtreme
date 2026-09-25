#pragma once

#include "RexGarageViewModel.h"

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
} RexCampaignGarageApi;

#ifdef __cplusplus
}
#endif
