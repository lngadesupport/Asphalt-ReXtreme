#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_UPGRADE_UI_MAP_MAGIC 0x4D555852u /* RXUM */
#define CAMPAIGN_UPGRADE_UI_MAP_VERSION 1u
#define CAMPAIGN_UPGRADE_UI_MAP_MAX_ENTRIES 1024u

typedef struct CampaignUpgradeUiEntry {
    int32_t ui_action_id;
    int32_t kind;
    int32_t part_slot;
    int32_t flags;
} CampaignUpgradeUiEntry;

int CampaignUpgradeUiMapEnsureLoaded(void);
const CampaignUpgradeUiEntry* CampaignUpgradeUiMapFind(int32_t ui_action_id);
uint32_t CampaignUpgradeUiMapCount(void);

#ifdef __cplusplus
}
#endif
