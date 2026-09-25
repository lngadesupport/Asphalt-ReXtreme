#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REX_CAMPAIGN_API_VERSION 1u
#define REX_CAMPAIGN_MAX_CARS 256u

enum RexIntentKind {
    REX_INTENT_BOOT = 1,
    REX_INTENT_ENTER_HOME = 2,
    REX_INTENT_SELECT_CAR = 10,
    REX_INTENT_BUILD_CAR = 11
};

enum RexGarageVisualMode {
    REX_GARAGE_HIDDEN = 0,
    REX_GARAGE_BUILD = 1,
    REX_GARAGE_OWNED = 2
};

typedef struct RexIntent {
    uint32_t size;
    uint32_t kind;
    int32_t value0;
    int32_t value1;
} RexIntent;

typedef struct RexViewState {
    uint32_t size;
    uint32_t revision;

    int32_t credits;
    int32_t tokens;

    int32_t selected_car;
    int32_t selected_car_owned;

    int32_t garage_visual_mode;
    int32_t garage_action_enabled;
    int32_t garage_busy;

    int32_t tutorial_stage;
    int32_t current_event;
} RexViewState;

int __cdecl RexCampaignBoot(void);
int __cdecl RexCampaignEnterHome(void);
int __cdecl RexCampaignSelectCar(int32_t car_id);
int __cdecl RexCampaignBuildCar(void);
int __cdecl RexCampaignDispatch(const RexIntent* intent);
int __cdecl RexCampaignReadView(RexViewState* out);

#ifdef __cplusplus
}
#endif
