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
int __cdecl CampaignFrontendBuildSelected(void) {
    return CampaignApplicationBuildSelected();
}
int __cdecl CampaignFrontendSelectCar(int32_t car_id) {
    return CampaignApplicationSelectCar(car_id);
}
