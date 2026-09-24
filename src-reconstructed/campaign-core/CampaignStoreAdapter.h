#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_STORE_LEGACY_MAGIC 0xC0DE5501u

typedef struct CampaignLegacyStoreArgs {
    const void* purchase_context;

    int32_t status;
    int32_t offer_id;
    int32_t item_id;
    int32_t balance_before;
    int32_t balance_after;
    uint32_t revision;
} CampaignLegacyStoreArgs;

uint32_t __cdecl CampaignStoreKeyHash(const char* key);
int __cdecl CampaignPurchaseLegacyStore(CampaignLegacyStoreArgs* args);

#ifdef __cplusplus
}
#endif
