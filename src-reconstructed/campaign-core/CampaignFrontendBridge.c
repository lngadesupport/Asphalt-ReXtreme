#include <stdint.h>
#include "CampaignFrontendBridge.h"
#include "CampaignCore.h"
#include "CampaignEventBus.h"
#include "CampaignUiService.h"
#include "CampaignOnlinePolicy.h"

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

static int ExecuteCore(
    CampaignFrontendRequest* r,
    uint32_t op,
    int32_t a,
    int32_t b,
    int32_t c,
    int32_t d
) {
    CampaignCommand cmd;

    ZeroBytes(&cmd, (uint32_t)sizeof(cmd));
    cmd.size = (uint32_t)sizeof(cmd);
    cmd.op = op;
    cmd.a = a;
    cmd.b = b;
    cmd.c = c;
    cmd.d = d;

    if (!CampaignExecuteCommand(&cmd) || !cmd.status) {
        r->status = 0;
        r->revision = cmd.revision;
        return 0;
    }

    r->status = 1;
    r->out0 = cmd.out0;
    r->out1 = cmd.out1;
    r->out2 = cmd.out2;
    r->revision = cmd.revision;
    return 1;
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
        CampaignEventReset();
        PublishSimple(CAMPAIGN_EVENT_PROFILE_READY, 0, 0);
        r->status = 1;
        return 1;

    case CAMPAIGN_FRONTEND_PROFILE_READY:
        PublishSimple(CAMPAIGN_EVENT_PROFILE_READY, 0, 0);
        r->status = 1;
        return 1;

    case CAMPAIGN_FRONTEND_ENTER_LOBBY:
        PublishSimple(CAMPAIGN_EVENT_LOBBY_READY, 0, 0);
        r->status = 1;
        return 1;

    case CAMPAIGN_FRONTEND_BUILD_CAR:
        if (!ExecuteCore(r, CAMPAIGN_OP_CRAFT_CAR, r->a, 0, 0, 0)) return 0;
        PublishSimple(CAMPAIGN_EVENT_OWNERSHIP_CHANGED, r->a, 1);
        return 1;

    case CAMPAIGN_FRONTEND_QUERY_OWNERSHIP:
        return ExecuteCore(r, CAMPAIGN_OP_IS_OWNED, r->a, 0, 0, 0);

    case CAMPAIGN_FRONTEND_START_EVENT:
        return ExecuteCore(r, CAMPAIGN_OP_BEGIN_EVENT_RACE, r->a, r->b, 0, 0);

    case CAMPAIGN_FRONTEND_FINISH_EVENT:
        if (!ExecuteCore(r, CAMPAIGN_OP_FINISH_EVENT_RACE, r->a, r->b, r->c, r->d)) return 0;
        PublishSimple(CAMPAIGN_EVENT_RACE_COMPLETED, r->out2, r->out0);
        return 1;

    case CAMPAIGN_FRONTEND_APPLY_UPGRADE:
        if (!ExecuteCore(r, CAMPAIGN_OP_APPLY_UPGRADE_UI, r->a, r->b, r->c, 0)) return 0;
        PublishSimple(CAMPAIGN_EVENT_UPGRADE_CHANGED, r->a, r->b);
        return 1;

    case CAMPAIGN_FRONTEND_PURCHASE_OFFER:
        if (!ExecuteCore(r, CAMPAIGN_OP_PURCHASE_OFFER, r->a, 0, 0, 0)) return 0;
        PublishSimple(CAMPAIGN_EVENT_STORE_CHANGED, r->out0, r->out2);
        return 1;

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
