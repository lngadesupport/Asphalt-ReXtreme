#include <stdint.h>
#include "RexCampaign.h"
#include "RexState.h"

int __cdecl RexCampaignBoot(void) {
    return RexStateBoot();
}
int __cdecl RexCampaignEnterHome(void) {
    return RexStateBoot();
}
int __cdecl RexCampaignSelectCar(int32_t car_id) {
    return RexStateSelectCar(car_id);
}
int __cdecl RexCampaignBuildCar(void) {
    return RexStateBuildSelected();
}
int __cdecl RexCampaignDispatch(const RexIntent* intent) {
    if(!intent || intent->size<(uint32_t)sizeof(*intent)) return 0;

    switch(intent->kind) {
    case REX_INTENT_BOOT:
        return RexCampaignBoot();
    case REX_INTENT_ENTER_HOME:
        return RexCampaignEnterHome();
    case REX_INTENT_SELECT_CAR:
        return RexCampaignSelectCar(intent->value0);
    case REX_INTENT_BUILD_CAR:
        return RexCampaignBuildCar();
    default:
        return 0;
    }
}
int __cdecl RexCampaignReadView(RexViewState* out) {
    return RexStateRead(out);
}
