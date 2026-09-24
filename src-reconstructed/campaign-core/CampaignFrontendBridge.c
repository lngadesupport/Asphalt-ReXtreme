#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignFrontendBridge.h"
#include "CampaignCore.h"
#include "CampaignServices.h"
#include "CampaignEventBus.h"
#include "CampaignUiService.h"
#include "CampaignOnlinePolicy.h"
#include "CampaignStartupService.h"

static void ZeroBytes(void* p, uint32_t count) {
    volatile unsigned char* q = (volatile unsigned char*)p;
    uint32_t i;
    for (i = 0; i < count; ++i) q[i] = 0;
}

static void PublishSimple(uint32_t type, int32_t a, int32_t b) {
    CampaignEvent ev;
    ZeroBytes(&ev, (uint32_t)sizeof(ev));
    ev.size = (uint32_t)sizeof(ev);
    ev.type = type;
    ev.a = a;
    ev.b = b;
    CampaignEventPublish(&ev);
}

int __cdecl CampaignFrontendSubmit(CampaignFrontendRequest* r) {
    if (!r || r->size < (uint32_t)sizeof(CampaignFrontendRequest)) return 0;

    r->status = 0;
    r->out0 = 0;
    r->out1 = 0;
    r->out2 = 0;
    r->revision = 0;

    switch (r->type) {
    case CAMPAIGN_FRONTEND_BOOT:
        if (!CampaignStartupBegin()) return 0;
        r->status = 1;
        return 1;

    case CAMPAIGN_FRONTEND_PROFILE_READY:
        PublishSimple(CAMPAIGN_EVENT_PROFILE_READY, 0, 0);
        r->status = 1;
        return 1;

    case CAMPAIGN_FRONTEND_ENTER_LOBBY:
        if (!CampaignStartupEnterLobby()) return 0;
        r->status = 1;
        return 1;

    case CAMPAIGN_FRONTEND_BUILD_CAR:
        {
            CampaignGarageResult out;
            ZeroBytes(&out, (uint32_t)sizeof(out));
            out.size = (uint32_t)sizeof(out);
            if (!CampaignServiceGarageAcquire(r->a, &out)) return 0;
            r->status = 1;
            r->out0 = out.owned;
            r->out1 = out.balance_before;
            r->out2 = out.balance_after;
            r->revision = out.revision;
            return 1;
        }

    case CAMPAIGN_FRONTEND_QUERY_OWNERSHIP:
        {
            CampaignGarageResult out;
            ZeroBytes(&out, (uint32_t)sizeof(out));
            out.size = (uint32_t)sizeof(out);
            if (!CampaignServiceGarageIsOwned(r->a, &out)) return 0;
            r->status = 1;
            r->out0 = out.owned;
            r->revision = out.revision;
            return 1;
        }

    case CAMPAIGN_FRONTEND_START_EVENT:
        {
            uint32_t session_id = 0;
            if (!CampaignServiceCareerStart(r->a, r->b, &session_id)) return 0;
            r->status = 1;
            r->out0 = (int32_t)session_id;
            return 1;
        }

    case CAMPAIGN_FRONTEND_FINISH_EVENT:
        {
            CampaignRaceResult out;
            ZeroBytes(&out, (uint32_t)sizeof(out));
            out.size = (uint32_t)sizeof(out);
            if (!CampaignServiceCareerFinish((uint32_t)r->a, r->b, r->c, r->d, &out)) return 0;
            r->status = 1;
            r->out0 = out.credits_awarded;
            r->out1 = out.premium_awarded;
            r->out2 = out.stars_awarded;
            r->revision = out.revision;
            return 1;
        }

    case CAMPAIGN_FRONTEND_APPLY_UPGRADE:
        {
            CampaignUpgradeResult out;
            ZeroBytes(&out, (uint32_t)sizeof(out));
            out.size = (uint32_t)sizeof(out);
            if (!CampaignServiceUpgradeApply(r->a, r->b, &out)) return 0;
            r->status = 1;
            r->out0 = out.target_level;
            r->out1 = out.balance_before;
            r->out2 = out.balance_after;
            r->revision = out.revision;
            return 1;
        }

    case CAMPAIGN_FRONTEND_PURCHASE_OFFER:
        {
            CampaignStoreResult out;
            ZeroBytes(&out, (uint32_t)sizeof(out));
            out.size = (uint32_t)sizeof(out);
            if (!CampaignServiceStorePurchase(r->a, &out)) return 0;
            r->status = 1;
            r->out0 = out.item_id;
            r->out1 = out.balance_before;
            r->out2 = out.balance_after;
            r->revision = out.revision;
            return 1;
        }

    case CAMPAIGN_FRONTEND_OPEN_GARAGE:
    case CAMPAIGN_FRONTEND_OPEN_STORE:
    case CAMPAIGN_FRONTEND_UI_ACK:
        r->status = 1;
        return 1;

    default:
        return 0;
    }
}

int __cdecl CampaignFrontendPoll(CampaignEvent* event) {
    return CampaignEventPoll(event);
}


int __cdecl CampaignFrontendBoot(void) {
    CampaignFrontendRequest request;
    ZeroBytes(&request, (uint32_t)sizeof(request));
    request.size = (uint32_t)sizeof(request);
    request.type = CAMPAIGN_FRONTEND_BOOT;
    return CampaignFrontendSubmit(&request);
}

int __cdecl CampaignFrontendLobbyReady(void) {
    CampaignFrontendRequest request;
    ZeroBytes(&request, (uint32_t)sizeof(request));
    request.size = (uint32_t)sizeof(request);
    request.type = CAMPAIGN_FRONTEND_ENTER_LOBBY;
    return CampaignFrontendSubmit(&request);
}


static int32_t CampaignFrontendSelectedCarId(void* gs_garage) {
    unsigned char* gs = (unsigned char*)gs_garage;
    void* holder;
    void* selected;

    if (!gs) return 0;
    holder = *(void**)(gs + 0x2D4);
    if (!holder) return 0;
    selected = *(void**)holder;
    if (!selected) return 0;
    return *(int32_t*)((unsigned char*)selected + 0xC0);
}

int __cdecl CampaignFrontendGarageBuild(void* gs_garage) {
    CampaignGarageResult out;
    int32_t car_id;

    car_id = CampaignFrontendSelectedCarId(gs_garage);
    if (car_id <= 0) return 0;

    ZeroBytes(&out, (uint32_t)sizeof(out));
    out.size = (uint32_t)sizeof(out);

    if (!CampaignServiceGarageAcquire(car_id, &out)) return 0;
    return out.owned ? 1 : 0;
}



int __cdecl CampaignFrontendIsOwned(int32_t car_id) {
    CampaignGarageResult out;

    if (car_id <= 0) return 0;

    ZeroBytes(&out, (uint32_t)sizeof(out));
    out.size = (uint32_t)sizeof(out);
    if (!CampaignServiceGarageIsOwned(car_id, &out)) return 0;
    return out.owned ? 1 : 0;
}
