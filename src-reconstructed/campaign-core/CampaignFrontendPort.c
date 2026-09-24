#include <stdint.h>
#include "CampaignFrontendPort.h"
#include "CampaignCore.h"
#include "CampaignServices.h"

static CampaignFrontendViewModel g_view;
static uint32_t g_frontend_revision;

static void ZeroBytes(void* p, uint32_t count) {
    volatile unsigned char* q=(volatile unsigned char*)p;
    uint32_t i;
    for(i=0;i<count;++i) q[i]=0;
}

static void CopyView(CampaignFrontendViewModel* out) {
    if (!out || out->size < (uint32_t)sizeof(*out)) return;
    *out = g_view;
}

static void RefreshEconomy(void) {
    CampaignEconomySnapshot e;
    ZeroBytes(&e,(uint32_t)sizeof(e));
    e.size=(uint32_t)sizeof(e);
    if (CampaignServiceEconomyGet(&e)) {
        g_view.credits=e.credits;
        g_view.premium_currency=e.premium;
    }
}

static void Bump(void) {
    ++g_frontend_revision;
    if (!g_frontend_revision) ++g_frontend_revision;
    g_view.revision=g_frontend_revision;
}

int __cdecl CampaignFrontendReadView(CampaignFrontendViewModel* out_view) {
    if (!out_view || out_view->size < (uint32_t)sizeof(*out_view)) return 0;
    CopyView(out_view);
    return 1;
}

int __cdecl CampaignFrontendDispatch(
    const CampaignFrontendIntent* intent,
    CampaignFrontendViewModel* out_view
) {
    CampaignGarageResult garage;

    if (!intent || intent->size < (uint32_t)sizeof(*intent)) return 0;

    switch (intent->type) {
    case CAMPAIGN_INTENT_BOOT:
        if (!CampaignServiceBoot()) return 0;
        ZeroBytes(&g_view,(uint32_t)sizeof(g_view));
        g_view.size=(uint32_t)sizeof(g_view);
        g_view.selected_car_id=-1;
        g_view.current_event_id=-1;
        RefreshEconomy();
        Bump();
        break;

    case CAMPAIGN_INTENT_ENTER_LOBBY:
        Bump();
        break;

    case CAMPAIGN_INTENT_OPEN_GARAGE:
        g_view.selected_car_id=intent->a;
        g_view.selected_car_owned=
            intent->a>0 ? CampaignServiceGarageIsOwned(intent->a) : 0;
        g_view.garage_build_enabled=
            intent->a>0 && !g_view.selected_car_owned;
        g_view.garage_build_busy=0;
        Bump();
        break;

    case CAMPAIGN_INTENT_SELECT_CAR:
        g_view.selected_car_id=intent->a;
        g_view.selected_car_owned=
            intent->a>0 ? CampaignServiceGarageIsOwned(intent->a) : 0;
        g_view.garage_build_enabled=
            intent->a>0 && !g_view.selected_car_owned;
        g_view.garage_build_busy=0;
        Bump();
        break;

    case CAMPAIGN_INTENT_BUILD_SELECTED_CAR:
        if (g_view.selected_car_id <= 0) return 0;

        ZeroBytes(&garage,(uint32_t)sizeof(garage));
        garage.size=(uint32_t)sizeof(garage);

        g_view.garage_build_busy=1;
        Bump();

        if (!CampaignServiceGarageAcquire(g_view.selected_car_id,&garage)) {
            g_view.garage_build_busy=0;
            g_view.notice_id=1;
            g_view.notice_arg=g_view.selected_car_id;
            Bump();
            break;
        }

        g_view.selected_car_owned=1;
        g_view.garage_build_enabled=0;
        g_view.garage_build_busy=0;

        /*
          Tutorial transition is Campaign-owned.
          No original CraftCar/build/completion/tutorial callback participates.
        */
        if (g_view.tutorial_blocking) {
            ++g_view.tutorial_step;
            g_view.tutorial_blocking=0;
        }

        RefreshEconomy();
        Bump();
        break;

    default:
        return 0;
    }

    if (out_view && out_view->size >= (uint32_t)sizeof(*out_view)) {
        CopyView(out_view);
    }
    return 1;
}
