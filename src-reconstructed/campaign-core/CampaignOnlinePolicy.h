#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum CampaignOnlineDomain {
    CAMPAIGN_ONLINE_NONE = 0,
    CAMPAIGN_ONLINE_CONNECTIVITY = 1,
    CAMPAIGN_ONLINE_PROFILE_SYNC = 2,
    CAMPAIGN_ONLINE_GLOBAL_SYNC = 3,
    CAMPAIGN_ONLINE_IAP = 4,
    CAMPAIGN_ONLINE_ADS = 5,
    CAMPAIGN_ONLINE_SOCIAL = 6,
    CAMPAIGN_ONLINE_LEADERBOARD = 7,
    CAMPAIGN_ONLINE_MULTIPLAYER = 8,
    CAMPAIGN_ONLINE_PUSH = 9,
    CAMPAIGN_ONLINE_TELEMETRY = 10,
    CAMPAIGN_ONLINE_REMOTE_CONFIG = 11,
    CAMPAIGN_ONLINE_CUSTOMER_CARE = 12
};

enum CampaignOnlineAction {
    CAMPAIGN_ONLINE_ACTION_LOCAL_SUCCESS = 1,
    CAMPAIGN_ONLINE_ACTION_LOCAL_NOOP = 2,
    CAMPAIGN_ONLINE_ACTION_HIDE_UI = 3,
    CAMPAIGN_ONLINE_ACTION_UNSUPPORTED_LOCAL = 4
};

typedef struct CampaignOnlineDecision {
    uint32_t size;
    uint32_t domain;
    uint32_t action;
    int32_t result_code;
    int32_t emit_event;
} CampaignOnlineDecision;

int __cdecl CampaignOnlineResolve(CampaignOnlineDecision* decision);
int __cdecl CampaignOnlineIsNetworkAllowed(void);

#ifdef __cplusplus
}
#endif
