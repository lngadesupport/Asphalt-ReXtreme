#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_RUNTIME_CATALOG_MAGIC 0x54435852u
#define CAMPAIGN_RUNTIME_CATALOG_VERSION 1u
#define CAMPAIGN_RUNTIME_CATALOG_MAX 256u

enum CampaignRuntimeAcquireType {
    CAMPAIGN_RUNTIME_ACQUIRE_NONE=0,
    CAMPAIGN_RUNTIME_ACQUIRE_BLUEPRINT=1,
    CAMPAIGN_RUNTIME_ACQUIRE_CREDITS=2,
    CAMPAIGN_RUNTIME_ACQUIRE_PREMIUM=3,
    CAMPAIGN_RUNTIME_ACQUIRE_FREE=4
};

typedef struct CampaignRuntimeRecipe {
    int32_t car_id;
    int32_t acquisition_type;
    int32_t item_id;
    int32_t cost;
    int32_t unlock_node_id;
    int32_t class_id;
    int32_t flags;
    int32_t reserved;
} CampaignRuntimeRecipe;

int __cdecl CampaignRuntimeCatalogLoad(void);
const CampaignRuntimeRecipe* __cdecl CampaignRuntimeCatalogFind(int32_t car_id);
const CampaignRuntimeRecipe* __cdecl CampaignRuntimeCatalogFirst(void);
uint32_t __cdecl CampaignRuntimeCatalogCount(void);

#ifdef __cplusplus
}
#endif
