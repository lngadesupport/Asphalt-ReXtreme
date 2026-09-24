#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum CampaignGarageFlowState {
    CAMPAIGN_GARAGE_IDLE = 0,
    CAMPAIGN_GARAGE_BUILDING = 1,
    CAMPAIGN_GARAGE_COMMITTED = 2,
    CAMPAIGN_GARAGE_FRONTEND_COMPLETED = 3,
    CAMPAIGN_GARAGE_FAILED = 4
};

typedef struct CampaignGarageFlowSnapshot {
    uint32_t size;
    uint32_t state;
    int32_t car_id;
    int32_t result;
    uint32_t revision;
} CampaignGarageFlowSnapshot;

void __cdecl CampaignGarageFlowBegin(int32_t car_id);
void __cdecl CampaignGarageFlowCommit(int32_t car_id, uint32_t revision);
void __cdecl CampaignGarageFlowFrontendCompleted(int32_t car_id, uint32_t revision);
void __cdecl CampaignGarageFlowFail(int32_t car_id);
int __cdecl CampaignGarageFlowGet(CampaignGarageFlowSnapshot* out);
void __cdecl CampaignGarageFlowReset(void);

#ifdef __cplusplus
}
#endif
