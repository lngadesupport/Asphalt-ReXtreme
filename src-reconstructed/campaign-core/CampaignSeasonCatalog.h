#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_SEASON_MAGIC 0x53435852u /* RXCS */
#define CAMPAIGN_SEASON_VERSION 1u
#define CAMPAIGN_SEASON_MAX 64u
#define CAMPAIGN_SEASON_EVENT_MAX 32u

typedef struct CampaignSeasonDefinition {
    int32_t season_id;
    int32_t required_node_id;
    uint32_t event_count;
    uint32_t flags;
    int32_t event_ids[CAMPAIGN_SEASON_EVENT_MAX];
} CampaignSeasonDefinition;

int CampaignSeasonCatalogEnsureLoaded(void);
uint32_t CampaignSeasonCatalogCount(void);
const CampaignSeasonDefinition* CampaignSeasonCatalogGet(uint32_t index);
const CampaignSeasonDefinition* CampaignSeasonCatalogFind(int32_t season_id);

#ifdef __cplusplus
}
#endif
