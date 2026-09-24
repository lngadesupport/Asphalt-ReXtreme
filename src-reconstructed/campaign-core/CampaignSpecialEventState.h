#pragma once
#include <stdint.h>
#include "CampaignSpecialEventCatalog.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_SPECIAL_EVENT_PERIOD_STATE_VERSION 1u

int CampaignSpecialEventPeriodStateEvaluate(
    const CampaignSpecialEventDefinition* def,
    uint32_t day_key,
    const uint32_t* completion_counts,
    uint32_t completion_count,
    uint32_t* completed_mask,
    uint32_t* completed_count
);
int CampaignSpecialEventPeriodStateReload(void);
int CampaignSpecialEventPeriodStateReset(void);

#ifdef __cplusplus
}
#endif
