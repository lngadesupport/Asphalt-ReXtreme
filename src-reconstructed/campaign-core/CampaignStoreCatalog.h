#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_STORE_CATALOG_MAGIC 0x53535852u
#define CAMPAIGN_STORE_CATALOG_VERSION 1u
#define CAMPAIGN_STORE_CATALOG_MAX_OFFERS 512u

enum CampaignStoreCurrency {
    CAMPAIGN_STORE_CURRENCY_CREDITS = 1,
    CAMPAIGN_STORE_CURRENCY_PREMIUM = 2,
    CAMPAIGN_STORE_CURRENCY_FREE = 3
};

typedef struct CampaignStoreOffer {
    int32_t offer_id;
    int32_t item_id;
    int32_t quantity;
    int32_t currency_type;
    int32_t price;
    int32_t unlock_node_id;
    int32_t flags;
    int32_t reserved;
} CampaignStoreOffer;

int CampaignStoreCatalogEnsureLoaded(void);
const CampaignStoreOffer* CampaignStoreCatalogFind(int32_t offer_id);
uint32_t CampaignStoreCatalogCount(void);

#ifdef __cplusplus
}
#endif
