#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_EVENT_BUS_CAPACITY 64u

enum CampaignEventType {
    CAMPAIGN_EVENT_NONE = 0,
    CAMPAIGN_EVENT_PROFILE_READY = 1,
    CAMPAIGN_EVENT_LOBBY_READY = 2,
    CAMPAIGN_EVENT_CURRENCY_CHANGED = 3,
    CAMPAIGN_EVENT_OWNERSHIP_CHANGED = 4,
    CAMPAIGN_EVENT_UPGRADE_CHANGED = 5,
    CAMPAIGN_EVENT_RACE_COMPLETED = 6,
    CAMPAIGN_EVENT_STORE_CHANGED = 7,
    CAMPAIGN_EVENT_BUILD_STARTED = 8,
    CAMPAIGN_EVENT_BUILD_COMPLETED = 9,
    CAMPAIGN_EVENT_BUILD_FAILED = 10,
    CAMPAIGN_EVENT_UI_NOTICE = 20,
    CAMPAIGN_EVENT_ONLINE_REQUEST_RETIRED = 30
};

typedef struct CampaignEvent {
    uint32_t size;
    uint32_t type;
    uint32_t sequence;
    int32_t a;
    int32_t b;
    int32_t c;
    int32_t d;
} CampaignEvent;

int __cdecl CampaignEventPublish(const CampaignEvent* event);
int __cdecl CampaignEventPoll(CampaignEvent* event);
uint32_t __cdecl CampaignEventPendingCount(void);
void __cdecl CampaignEventReset(void);

#ifdef __cplusplus
}
#endif
