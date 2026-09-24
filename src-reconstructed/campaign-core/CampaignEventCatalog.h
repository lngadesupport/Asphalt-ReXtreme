#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_EVENT_CATALOG_MAGIC 0x45435852u /* RXCE */
#define CAMPAIGN_EVENT_CATALOG_VERSION 1u
#define CAMPAIGN_EVENT_CATALOG_MAX_EVENTS 512u

typedef struct CampaignEventDefinition {
    int32_t event_id;
    int32_t required_node_id;
    int32_t completion_node_id;

    int32_t participation_credits;
    int32_t position1_credits;
    int32_t position2_credits;
    int32_t position3_credits;

    int32_t premium_reward;
    int32_t max_stars;
    int32_t flags;
} CampaignEventDefinition;

int CampaignEventCatalogEnsureLoaded(void);
const CampaignEventDefinition* CampaignEventCatalogFind(int32_t event_id);
uint32_t CampaignEventCatalogCount(void);

#ifdef __cplusplus
}
#endif
