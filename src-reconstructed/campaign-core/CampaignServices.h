#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct CampaignEconomySnapshot {
    uint32_t size;
    int32_t credits;
    int32_t premium;
    uint32_t revision;
} CampaignEconomySnapshot;

typedef struct CampaignGarageResult {
    uint32_t size;
    int32_t car_id;
    int32_t owned;
    int32_t acquisition_type;
    int32_t balance_before;
    int32_t balance_after;
    uint32_t revision;
} CampaignGarageResult;

typedef struct CampaignRaceResult {
    uint32_t size;
    uint32_t session_id;
    int32_t credits_awarded;
    int32_t premium_awarded;
    int32_t stars_awarded;
    uint32_t revision;
} CampaignRaceResult;

typedef struct CampaignUpgradeResult {
    uint32_t size;
    int32_t car_id;
    int32_t action_id;
    int32_t target_level;
    int32_t balance_before;
    int32_t balance_after;
    uint32_t revision;
} CampaignUpgradeResult;

typedef struct CampaignStoreResult {
    uint32_t size;
    int32_t offer_id;
    int32_t item_id;
    int32_t balance_before;
    int32_t balance_after;
    uint32_t revision;
} CampaignStoreResult;

int __cdecl CampaignServiceBoot(void);
int __cdecl CampaignServiceEconomyGet(CampaignEconomySnapshot* out);
int __cdecl CampaignServiceGarageIsOwned(int32_t car_id, CampaignGarageResult* out);
int __cdecl CampaignServiceGarageAcquire(int32_t car_id, CampaignGarageResult* out);
int __cdecl CampaignServiceCareerStart(int32_t event_id, int32_t car_id, uint32_t* session_id);
int __cdecl CampaignServiceCareerFinish(
    uint32_t session_id,
    int32_t position,
    int32_t stars,
    int32_t finish_time_ms,
    CampaignRaceResult* out
);
int __cdecl CampaignServiceUpgradeApply(
    int32_t car_id,
    int32_t action_id,
    CampaignUpgradeResult* out
);
int __cdecl CampaignServiceStorePurchase(int32_t offer_id, CampaignStoreResult* out);

#ifdef __cplusplus
}
#endif
