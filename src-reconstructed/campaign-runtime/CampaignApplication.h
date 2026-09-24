#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum CampaignIntentType {
    CAMPAIGN_INTENT_NONE=0,
    CAMPAIGN_INTENT_BOOT=1,
    CAMPAIGN_INTENT_ENTER_LOBBY=2,
    CAMPAIGN_INTENT_SELECT_CAR=10,
    CAMPAIGN_INTENT_BUILD_SELECTED_CAR=11
};

typedef struct CampaignIntent {
    uint32_t size;
    uint32_t type;
    int32_t a;
    int32_t b;
    int32_t c;
    int32_t d;
} CampaignIntent;

typedef struct CampaignViewModel {
    uint32_t size;
    uint32_t revision;
    int32_t credits;
    int32_t premium;
    int32_t selected_car_id;
    int32_t selected_car_owned;
    int32_t build_visible;
    int32_t build_enabled;
    int32_t build_busy;
    int32_t tutorial_step;
    int32_t current_event_id;
    int32_t notice_id;
} CampaignViewModel;

int __cdecl CampaignApplicationDispatch(
    const CampaignIntent* intent,
    CampaignViewModel* out
);
int __cdecl CampaignApplicationRead(CampaignViewModel* out);
int __cdecl CampaignApplicationBuildSelected(void);
int __cdecl CampaignApplicationSelectCar(int32_t car_id);

#ifdef __cplusplus
}
#endif
