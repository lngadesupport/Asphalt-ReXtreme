#include <stdint.h>
#include "CampaignOnlinePolicy.h"
#include "CampaignEventBus.h"

int __cdecl CampaignOnlineIsNetworkAllowed(void) {
    return 0;
}

static void PublishRetired(uint32_t domain, uint32_t action) {
    CampaignEvent ev;
    ev.size = (uint32_t)sizeof(ev);
    ev.type = CAMPAIGN_EVENT_ONLINE_REQUEST_RETIRED;
    ev.sequence = 0;
    ev.a = (int32_t)domain;
    ev.b = (int32_t)action;
    ev.c = 0;
    ev.d = 0;
    CampaignEventPublish(&ev);
}

int __cdecl CampaignOnlineResolve(CampaignOnlineDecision* decision) {
    uint32_t action;

    if (!decision || decision->size < (uint32_t)sizeof(CampaignOnlineDecision)) return 0;

    switch (decision->domain) {
    case CAMPAIGN_ONLINE_CONNECTIVITY:
    case CAMPAIGN_ONLINE_PROFILE_SYNC:
    case CAMPAIGN_ONLINE_GLOBAL_SYNC:
        action = CAMPAIGN_ONLINE_ACTION_LOCAL_SUCCESS;
        decision->result_code = 0;
        break;

    case CAMPAIGN_ONLINE_IAP:
    case CAMPAIGN_ONLINE_ADS:
    case CAMPAIGN_ONLINE_PUSH:
    case CAMPAIGN_ONLINE_TELEMETRY:
    case CAMPAIGN_ONLINE_REMOTE_CONFIG:
        action = CAMPAIGN_ONLINE_ACTION_LOCAL_NOOP;
        decision->result_code = 0;
        break;

    case CAMPAIGN_ONLINE_SOCIAL:
    case CAMPAIGN_ONLINE_LEADERBOARD:
    case CAMPAIGN_ONLINE_MULTIPLAYER:
    case CAMPAIGN_ONLINE_CUSTOMER_CARE:
        action = CAMPAIGN_ONLINE_ACTION_UNSUPPORTED_LOCAL;
        decision->result_code = 0;
        break;

    default:
        return 0;
    }

    decision->action = action;
    decision->emit_event = 1;
    PublishRetired(decision->domain, action);
    return 1;
}
