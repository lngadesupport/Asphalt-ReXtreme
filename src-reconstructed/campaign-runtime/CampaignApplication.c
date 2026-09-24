#include <stdint.h>
#include "CampaignApplication.h"
#include "CampaignRuntimeState.h"

static CampaignViewModel g_view;

static void Zero(void* p,uint32_t n) {
    volatile unsigned char* q=(volatile unsigned char*)p;
    uint32_t i; for(i=0;i<n;++i) q[i]=0;
}
static int Refresh(void) {
    CampaignRuntimeSnapshot s;
    Zero(&s,(uint32_t)sizeof(s));
    s.size=(uint32_t)sizeof(s);
    if(!CampaignRuntimeRead(&s)) return 0;

    g_view.size=(uint32_t)sizeof(g_view);
    g_view.revision=s.revision;
    g_view.credits=s.credits;
    g_view.premium=s.premium;
    g_view.selected_car_id=s.selected_car_id;
    g_view.selected_car_owned=
        s.selected_car_id>0 ? CampaignRuntimeIsOwned(s.selected_car_id) : 0;
    g_view.build_visible=1;
    g_view.build_enabled=
        s.selected_car_id>0 && !g_view.selected_car_owned;
    g_view.build_busy=0;
    g_view.tutorial_step=s.tutorial_step;
    g_view.current_event_id=s.current_event_id;
    return 1;
}
static void Copy(CampaignViewModel* out) {
    if(out && out->size>=(uint32_t)sizeof(*out)) *out=g_view;
}

int __cdecl CampaignApplicationRead(CampaignViewModel* out) {
    if(!out || out->size<(uint32_t)sizeof(*out)) return 0;
    if(!Refresh()) return 0;
    Copy(out); return 1;
}
int __cdecl CampaignApplicationSelectCar(int32_t car_id) {
    if(!CampaignRuntimeSelectCar(car_id)) return 0;
    return Refresh();
}
int __cdecl CampaignApplicationBuildSelected(void) {
    /*
      Straight local path:
      intent -> runtime -> save -> view model.
      No original gameplay object, callback, signal, completion or service.
    */
    if(!CampaignRuntimeBuildSelected()) {
        Refresh();
        g_view.notice_id=1;
        return 0;
    }
    return Refresh();
}
int __cdecl CampaignApplicationDispatch(
    const CampaignIntent* intent,
    CampaignViewModel* out
) {
    if(!intent || intent->size<(uint32_t)sizeof(*intent)) return 0;

    switch(intent->type) {
    case CAMPAIGN_INTENT_BOOT:
        if(!CampaignRuntimeBoot()) return 0;
        if(!Refresh()) return 0;
        break;
    case CAMPAIGN_INTENT_ENTER_LOBBY:
        if(!Refresh()) return 0;
        break;
    case CAMPAIGN_INTENT_SELECT_CAR:
        if(!CampaignApplicationSelectCar(intent->a)) return 0;
        break;
    case CAMPAIGN_INTENT_BUILD_SELECTED_CAR:
        if(!CampaignApplicationBuildSelected()) {
            Copy(out);
            return 0;
        }
        break;
    default:
        return 0;
    }

    Copy(out);
    return 1;
}
