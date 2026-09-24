#include <stdint.h>
#include "CampaignFeaturePolicy.h"

int __cdecl CampaignFeatureQueryLocal(CampaignFeatureQuery* q) {
    if (!q || q->size < (uint32_t)sizeof(*q)) return 0;

    q->enabled = 0;
    q->local_only = 1;
    q->visible = 0;

    switch (q->feature_id) {
    case CAMPAIGN_FEATURE_CAREER:
    case CAMPAIGN_FEATURE_GARAGE:
    case CAMPAIGN_FEATURE_ECONOMY:
        q->enabled = 1;
        q->visible = 1;
        return 1;

    case CAMPAIGN_FEATURE_UPGRADES:
    case CAMPAIGN_FEATURE_STORE_LOCAL:
    case CAMPAIGN_FEATURE_OBJECTIVES:
    case CAMPAIGN_FEATURE_LOCAL_EVENTS:
        /* Local subsystems exist but may still be data-gated during migration. */
        q->enabled = 0;
        q->visible = 1;
        return 1;

    case CAMPAIGN_FEATURE_MULTIPLAYER:
    case CAMPAIGN_FEATURE_MATCHMAKING:
    case CAMPAIGN_FEATURE_LEADERBOARDS:
    case CAMPAIGN_FEATURE_SOCIAL:
    case CAMPAIGN_FEATURE_ADS:
    case CAMPAIGN_FEATURE_IAP:
    case CAMPAIGN_FEATURE_CLOUD_SAVE:
    case CAMPAIGN_FEATURE_PUSH:
    case CAMPAIGN_FEATURE_REMOTE_EVENTS:
    case CAMPAIGN_FEATURE_REMOTE_CONFIG:
        /* These features do not exist in Campaign Edition. */
        q->enabled = 0;
        q->visible = 0;
        return 1;

    default:
        return 0;
    }
}
