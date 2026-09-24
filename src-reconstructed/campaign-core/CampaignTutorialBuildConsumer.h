#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct CampaignTutorialBuildUiResult {
    uint32_t size;
    int32_t car_id;
    int32_t success;
    uint32_t revision;
    uint32_t pending_object_before;
    uint32_t pending_control_before;
    uint32_t widget;
} CampaignTutorialBuildUiResult;

int __cdecl CampaignTutorialBuildComplete(
    void* gs_garage,
    int32_t car_id,
    int32_t success,
    uint32_t revision,
    CampaignTutorialBuildUiResult* out
);

#ifdef __cplusplus
}
#endif
