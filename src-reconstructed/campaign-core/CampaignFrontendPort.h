#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum CampaignFrontendIntentType {
    CAMPAIGN_INTENT_NONE = 0,
    CAMPAIGN_INTENT_BOOT = 1,
    CAMPAIGN_INTENT_ENTER_LOBBY = 2,
    CAMPAIGN_INTENT_OPEN_GARAGE = 10,
    CAMPAIGN_INTENT_BUILD_SELECTED_CAR = 11,
    CAMPAIGN_INTENT_SELECT_CAR = 12,
    CAMPAIGN_INTENT_START_EVENT = 20,
    CAMPAIGN_INTENT_FINISH_EVENT = 21,
    CAMPAIGN_INTENT_APPLY_UPGRADE = 30,
    CAMPAIGN_INTENT_PURCHASE_LOCAL_OFFER = 40,
    CAMPAIGN_INTENT_TUTORIAL_ACK = 50
};

typedef struct CampaignFrontendIntent {
    uint32_t size;
    uint32_t type;
    int32_t a;
    int32_t b;
    int32_t c;
    int32_t d;
} CampaignFrontendIntent;

typedef struct CampaignFrontendViewModel {
    uint32_t size;
    uint32_t revision;

    int32_t selected_car_id;
    int32_t selected_car_owned;
    int32_t garage_build_enabled;
    int32_t garage_build_busy;

    int32_t credits;
    int32_t premium_currency;

    int32_t tutorial_step;
    int32_t tutorial_blocking;

    int32_t current_event_id;
    int32_t current_event_state;

    int32_t notice_id;
    int32_t notice_arg;
} CampaignFrontendViewModel;

int __cdecl CampaignFrontendDispatch(
    const CampaignFrontendIntent* intent,
    CampaignFrontendViewModel* out_view
);

int __cdecl CampaignFrontendReadView(
    CampaignFrontendViewModel* out_view
);

#ifdef __cplusplus
}
#endif
