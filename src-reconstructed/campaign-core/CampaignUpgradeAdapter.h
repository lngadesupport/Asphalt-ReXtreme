#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct CampaignLegacyUpgradeSelectionArgs {
    int32_t car_id;
    const void* selection_object;

    int32_t status;
    int32_t applied_count;
    uint32_t revision;
} CampaignLegacyUpgradeSelectionArgs;

int __cdecl CampaignApplyLegacyUpgradeSelection(
    CampaignLegacyUpgradeSelectionArgs* args
);

#ifdef __cplusplus
}
#endif
