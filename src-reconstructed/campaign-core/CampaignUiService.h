#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum CampaignUiKind {
    CAMPAIGN_UI_NONE = 0,
    CAMPAIGN_UI_NOTICE = 1,
    CAMPAIGN_UI_CONFIRM = 2,
    CAMPAIGN_UI_REWARD = 3,
    CAMPAIGN_UI_CONNECTION_ERROR = 10,
    CAMPAIGN_UI_RETRY_CONNECTION = 11,
    CAMPAIGN_UI_CLOUD_SYNC = 12,
    CAMPAIGN_UI_ONLINE_REQUIRED = 13
};

typedef struct CampaignUiRequest {
    uint32_t size;
    uint32_t kind;
    int32_t message_id;
    int32_t a;
    int32_t b;
    int32_t status;
} CampaignUiRequest;

int __cdecl CampaignUiSubmit(CampaignUiRequest* request);
int __cdecl CampaignUiShouldSuppressLegacyKind(uint32_t kind);

#ifdef __cplusplus
}
#endif
