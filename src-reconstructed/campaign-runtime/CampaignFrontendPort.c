#include "CampaignFrontendPort.h"

int __cdecl CampaignFrontendDispatch(
    const CampaignIntent* intent,
    CampaignViewModel* out
) {
    return CampaignApplicationDispatch(intent,out);
}
int __cdecl CampaignFrontendRead(CampaignViewModel* out) {
    return CampaignApplicationRead(out);
}
int __cdecl CampaignFrontendBoot(void) {
    CampaignIntent intent;
    CampaignViewModel view;
    intent.size=(uint32_t)sizeof(intent);
    intent.type=CAMPAIGN_INTENT_BOOT;
    intent.a=intent.b=intent.c=intent.d=0;
    view.size=(uint32_t)sizeof(view);
    return CampaignApplicationDispatch(&intent,&view);
}
int __cdecl CampaignFrontendEnterLobby(void) {
    CampaignIntent intent;
    CampaignViewModel view;
    intent.size=(uint32_t)sizeof(intent);
    intent.type=CAMPAIGN_INTENT_ENTER_LOBBY;
    intent.a=intent.b=intent.c=intent.d=0;
    view.size=(uint32_t)sizeof(view);
    return CampaignApplicationDispatch(&intent,&view);
}
int __cdecl CampaignFrontendBuildSelected(void) {
    return CampaignApplicationBuildSelected();
}
int __cdecl CampaignFrontendSelectCar(int32_t car_id) {
    return CampaignApplicationSelectCar(car_id);
}
