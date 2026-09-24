#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_RUNTIME_MAX_OWNED 256u

typedef struct CampaignRuntimeSnapshot {
    uint32_t size;
    uint32_t revision;
    int32_t credits;
    int32_t premium;
    int32_t selected_car_id;
    int32_t tutorial_step;
    int32_t current_event_id;
    uint32_t owned_count;
} CampaignRuntimeSnapshot;

int __cdecl CampaignRuntimeBoot(void);
int __cdecl CampaignRuntimeRead(CampaignRuntimeSnapshot* out);
int __cdecl CampaignRuntimeSelectCar(int32_t car_id);
int __cdecl CampaignRuntimeIsOwned(int32_t car_id);
int __cdecl CampaignRuntimeBuildSelected(void);
int __cdecl CampaignRuntimeSetTutorialStep(int32_t step);
int __cdecl CampaignRuntimeSave(void);

#ifdef __cplusplus
}
#endif
