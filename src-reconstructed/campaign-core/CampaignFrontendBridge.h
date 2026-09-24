#pragma once
#include <stdint.h>
#include "CampaignEventBus.h"

#ifdef __cplusplus
extern "C" {
#endif

enum CampaignFrontendRequestType {
    CAMPAIGN_FRONTEND_NONE = 0,
    CAMPAIGN_FRONTEND_BOOT = 1,
    CAMPAIGN_FRONTEND_PROFILE_READY = 2,
    CAMPAIGN_FRONTEND_ENTER_LOBBY = 3,
    CAMPAIGN_FRONTEND_OPEN_GARAGE = 10,
    CAMPAIGN_FRONTEND_BUILD_CAR = 11,
    CAMPAIGN_FRONTEND_QUERY_OWNERSHIP = 12,
    CAMPAIGN_FRONTEND_START_EVENT = 20,
    CAMPAIGN_FRONTEND_FINISH_EVENT = 21,
    CAMPAIGN_FRONTEND_APPLY_UPGRADE = 30,
    CAMPAIGN_FRONTEND_OPEN_STORE = 40,
    CAMPAIGN_FRONTEND_PURCHASE_OFFER = 41,
    CAMPAIGN_FRONTEND_UI_ACK = 50
};

typedef struct CampaignFrontendRequest {
    uint32_t size;
    uint32_t type;
    int32_t a;
    int32_t b;
    int32_t c;
    int32_t d;
    int32_t status;
    int32_t out0;
    int32_t out1;
    int32_t out2;
    uint32_t revision;
} CampaignFrontendRequest;

int __cdecl CampaignFrontendSubmit(CampaignFrontendRequest* request);
int __cdecl CampaignFrontendPoll(CampaignEvent* event);

#ifdef __cplusplus
}
#endif
