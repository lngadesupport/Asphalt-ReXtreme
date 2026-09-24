#pragma once
#include <stdint.h>
#include "CampaignSpecialEventCatalog.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_SPECIAL_EVENT_PERIOD_STATE_VERSION 2u

int CampaignSpecialEventPeriodStateGet(
    const CampaignSpecialEventDefinition* def,
    uint32_t day_key,
    uint32_t* completed_mask,
    uint32_t* completed_count
);
int CampaignSpecialEventPeriodStateMarkStage(
    const CampaignSpecialEventDefinition* def,
    uint32_t period_key,
    uint32_t stage_index
);
int CampaignSpecialEventPeriodStateReload(void);
int CampaignSpecialEventPeriodStateReset(void);

#ifdef __cplusplus
}
#endif
