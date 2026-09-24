#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_SPECIAL_EVENT_MAGIC 0x53455852u /* RXES */
#define CAMPAIGN_SPECIAL_EVENT_VERSION 1u
#define CAMPAIGN_SPECIAL_EVENT_MAX 64u
#define CAMPAIGN_SPECIAL_EVENT_STAGE_MAX 16u

enum CampaignSpecialEventSchedule {
    CAMPAIGN_SPECIAL_EVENT_PERMANENT = 1,
    CAMPAIGN_SPECIAL_EVENT_DAILY = 2,
    CAMPAIGN_SPECIAL_EVENT_WEEKLY = 3,
    CAMPAIGN_SPECIAL_EVENT_MONTHLY = 4,
    CAMPAIGN_SPECIAL_EVENT_UNLOCK = 5,
    CAMPAIGN_SPECIAL_EVENT_MANUAL = 6
};

enum CampaignSpecialEventFlags {
    CAMPAIGN_SPECIAL_EVENT_MANUAL_ACTIVE = 1u << 0
};

typedef struct CampaignSpecialEventDefinition {
    int32_t special_event_id;
    uint32_t schedule;
    int32_t required_node_id;
    uint32_t stage_count;
    uint32_t start_day_key; /* YYYYMMDD, 0 = unbounded */
    uint32_t end_day_key;   /* YYYYMMDD, 0 = unbounded */
    uint32_t flags;
    uint32_t reserved;
    int32_t stage_event_ids[CAMPAIGN_SPECIAL_EVENT_STAGE_MAX];
} CampaignSpecialEventDefinition;

int CampaignSpecialEventCatalogEnsureLoaded(void);
uint32_t CampaignSpecialEventCatalogCount(void);
const CampaignSpecialEventDefinition* CampaignSpecialEventCatalogGet(uint32_t index);
const CampaignSpecialEventDefinition* CampaignSpecialEventCatalogFind(int32_t special_event_id);
int CampaignSpecialEventDateAvailable(
    const CampaignSpecialEventDefinition* def,
    uint32_t day_key
);
uint32_t CampaignSpecialEventPeriodKey(
    const CampaignSpecialEventDefinition* def,
    uint32_t day_key
);

#ifdef __cplusplus
}
#endif
