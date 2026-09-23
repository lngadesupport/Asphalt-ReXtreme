#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_UPGRADE_CATALOG_MAGIC 0x55435852u /* RXCU */
#define CAMPAIGN_UPGRADE_CATALOG_VERSION 1u
#define CAMPAIGN_UPGRADE_CATALOG_MAX_ENTRIES 4096u

enum CampaignUpgradeKind {
    CAMPAIGN_UPGRADE_KIND_STANDARD = 1,
    CAMPAIGN_UPGRADE_KIND_PROKIT = 2
};

enum CampaignCostType {
    CAMPAIGN_COST_CREDITS = 1,
    CAMPAIGN_COST_PREMIUM = 2,
    CAMPAIGN_COST_INVENTORY = 3,
    CAMPAIGN_COST_FREE = 4
};

typedef struct CampaignUpgradeDefinition {
    int32_t car_id;
    int32_t kind;
    int32_t part_slot;
    int32_t target_level;

    int32_t cost_type;
    int32_t item_id;
    int32_t cost;
    int32_t unlock_node_id;

    int32_t flags;
    int32_t reserved;
} CampaignUpgradeDefinition;

int CampaignUpgradeCatalogEnsureLoaded(void);
const CampaignUpgradeDefinition* CampaignUpgradeCatalogFind(
    int32_t car_id,
    int32_t kind,
    int32_t part_slot,
    int32_t target_level
);
uint32_t CampaignUpgradeCatalogCount(void);

#ifdef __cplusplus
}
#endif
