#pragma once
#include <stdint.h>
#include "CampaignObjectiveCatalog.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_LAST_RESULT_VERSION 1u

typedef struct CampaignLastResultSnapshot {
    uint32_t size;
    uint32_t version;
    uint32_t campaign_revision;
    int32_t event_id;
    int32_t car_id;
    uint32_t session_id;
    CampaignRaceMetrics metrics;
} CampaignLastResultSnapshot;

int CampaignLastResultEnsureLoaded(void);
int CampaignLastResultRecord(
    int32_t event_id,
    int32_t car_id,
    const CampaignRaceMetrics* metrics,
    uint32_t campaign_revision
);
int CampaignLastResultGet(CampaignLastResultSnapshot* out);
int CampaignLastResultClear(void);

#ifdef __cplusplus
}
#endif
