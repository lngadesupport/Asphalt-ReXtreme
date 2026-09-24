#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_ACTIVITY_CONTEXT_VERSION 1u

enum CampaignActivityType {
    CAMPAIGN_ACTIVITY_NONE = 0,
    CAMPAIGN_ACTIVITY_SPECIAL_EVENT = 1,
    CAMPAIGN_ACTIVITY_CHAMPIONSHIP = 2
};

typedef struct CampaignActivityContext {
    uint32_t size;
    uint32_t version;
    uint32_t session_id;
    uint32_t activity_type;
    int32_t activity_id;
    uint32_t slot_index;
    int32_t event_id;
    uint32_t period_key;
    int32_t result_placement;
    uint32_t result_valid;
} CampaignActivityContext;

int CampaignActivityContextSet(const CampaignActivityContext* context);
int CampaignActivityContextGet(CampaignActivityContext* out);
int CampaignActivityContextSetResult(uint32_t session_id, int32_t placement);
int CampaignActivityContextClear(uint32_t session_id);
int CampaignActivityContextReset(void);

#ifdef __cplusplus
}
#endif
