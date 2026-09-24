#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum CampaignFeatureId {
    CAMPAIGN_FEATURE_CAREER = 1,
    CAMPAIGN_FEATURE_GARAGE = 2,
    CAMPAIGN_FEATURE_ECONOMY = 3,
    CAMPAIGN_FEATURE_UPGRADES = 4,
    CAMPAIGN_FEATURE_STORE_LOCAL = 5,
    CAMPAIGN_FEATURE_OBJECTIVES = 6,
    CAMPAIGN_FEATURE_LOCAL_EVENTS = 7,

    CAMPAIGN_FEATURE_MULTIPLAYER = 100,
    CAMPAIGN_FEATURE_MATCHMAKING = 101,
    CAMPAIGN_FEATURE_LEADERBOARDS = 102,
    CAMPAIGN_FEATURE_SOCIAL = 103,
    CAMPAIGN_FEATURE_ADS = 104,
    CAMPAIGN_FEATURE_IAP = 105,
    CAMPAIGN_FEATURE_CLOUD_SAVE = 106,
    CAMPAIGN_FEATURE_PUSH = 107,
    CAMPAIGN_FEATURE_REMOTE_EVENTS = 108,
    CAMPAIGN_FEATURE_REMOTE_CONFIG = 109
};

typedef struct CampaignFeatureQuery {
    uint32_t size;
    uint32_t feature_id;
    int32_t enabled;
    int32_t local_only;
    int32_t visible;
} CampaignFeatureQuery;

int __cdecl CampaignFeatureQueryLocal(CampaignFeatureQuery* query);

#ifdef __cplusplus
}
#endif
