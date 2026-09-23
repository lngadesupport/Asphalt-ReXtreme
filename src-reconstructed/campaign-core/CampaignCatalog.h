#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_CATALOG_MAGIC 0x54435852u /* RXCT */
#define CAMPAIGN_CATALOG_VERSION 1u
#define CAMPAIGN_CATALOG_MAX_VEHICLES 256u

enum CampaignAcquisitionType {
    CAMPAIGN_ACQUIRE_NONE = 0,
    CAMPAIGN_ACQUIRE_BLUEPRINT = 1,
    CAMPAIGN_ACQUIRE_CREDITS = 2,
    CAMPAIGN_ACQUIRE_PREMIUM = 3,
    CAMPAIGN_ACQUIRE_FREE = 4
};

typedef struct CampaignVehicleRecipe {
    int32_t car_id;
    int32_t acquisition_type;
    int32_t item_id;
    int32_t cost;
    int32_t unlock_node_id;
    int32_t class_id;
    int32_t flags;
    int32_t reserved;
} CampaignVehicleRecipe;

int CampaignCatalogEnsureLoaded(void);
const CampaignVehicleRecipe* CampaignCatalogFind(int32_t car_id);
uint32_t CampaignCatalogCount(void);

#ifdef __cplusplus
}
#endif
