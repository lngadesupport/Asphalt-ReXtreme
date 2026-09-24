#include <stdint.h>
#include "CampaignServices.h"
#include "CampaignCore.h"
#include "CampaignEventBus.h"

static void ZeroBytes(void* p, uint32_t count) {
    volatile unsigned char* q = (volatile unsigned char*)p;
    uint32_t i;
    for (i = 0; i < count; ++i) q[i] = 0;
}

static int Run(CampaignCommand* cmd, uint32_t op, int32_t a, int32_t b, int32_t c, int32_t d) {
    ZeroBytes(cmd, (uint32_t)sizeof(*cmd));
    cmd->size = (uint32_t)sizeof(*cmd);
    cmd->op = op;
    cmd->a = a;
    cmd->b = b;
    cmd->c = c;
    cmd->d = d;
    return CampaignExecuteCommand(cmd) && cmd->status;
}

static void Publish(uint32_t type, int32_t a, int32_t b, int32_t c, int32_t d) {
    CampaignEvent ev;
    ZeroBytes(&ev, (uint32_t)sizeof(ev));
    ev.size = (uint32_t)sizeof(ev);
    ev.type = type;
    ev.a = a;
    ev.b = b;
    ev.c = c;
    ev.d = d;
    CampaignEventPublish(&ev);
}

int __cdecl CampaignServiceBoot(void) {
    CampaignCommand cmd;

    CampaignEventReset();

    if (!Run(&cmd, CAMPAIGN_OP_RELOAD, 0, 0, 0, 0)) return 0;

    Publish(CAMPAIGN_EVENT_PROFILE_READY, 0, 0, 0, 0);
    return 1;
}

int __cdecl CampaignServiceEconomyGet(CampaignEconomySnapshot* out) {
    CampaignCommand credits;
    CampaignCommand premium;

    if (!out || out->size < (uint32_t)sizeof(*out)) return 0;

    out->credits = 0;
    out->premium = 0;
    out->revision = 0;

    if (!Run(&credits, CAMPAIGN_OP_GET_CREDITS, 0, 0, 0, 0)) return 0;
    if (!Run(&premium, CAMPAIGN_OP_GET_PREMIUM, 0, 0, 0, 0)) return 0;

    out->credits = credits.out0;
    out->premium = premium.out0;
    out->revision = credits.revision > premium.revision ? credits.revision : premium.revision;
    return 1;
}

int __cdecl CampaignServiceGarageIsOwned(int32_t car_id, CampaignGarageResult* out) {
    CampaignCommand cmd;

    if (car_id <= 0 || !out || out->size < (uint32_t)sizeof(*out)) return 0;

    out->car_id = car_id;
    out->owned = 0;
    out->acquisition_type = 0;
    out->balance_before = 0;
    out->balance_after = 0;
    out->revision = 0;

    if (!Run(&cmd, CAMPAIGN_OP_IS_OWNED, car_id, 0, 0, 0)) return 0;

    out->owned = cmd.out0 ? 1 : 0;
    out->revision = cmd.revision;
    return 1;
}

int __cdecl CampaignServiceGarageAcquire(int32_t car_id, CampaignGarageResult* out) {
    CampaignCommand cmd;

    if (car_id <= 0 || !out || out->size < (uint32_t)sizeof(*out)) return 0;

    out->car_id = car_id;
    out->owned = 0;
    out->acquisition_type = 0;
    out->balance_before = 0;
    out->balance_after = 0;
    out->revision = 0;

    if (!Run(&cmd, CAMPAIGN_OP_ACQUIRE_CATALOG, car_id, 0, 0, 0)) return 0;

    out->owned = 1;
    out->acquisition_type = cmd.out0;
    out->balance_before = cmd.out1;
    out->balance_after = cmd.out2;
    out->revision = cmd.revision;

    Publish(CAMPAIGN_EVENT_OWNERSHIP_CHANGED, car_id, 1, cmd.out1, cmd.out2);
    return 1;
}

int __cdecl CampaignServiceCareerStart(int32_t event_id, int32_t car_id, uint32_t* session_id) {
    CampaignCommand cmd;

    if (event_id <= 0) return 0;
    if (!Run(&cmd, CAMPAIGN_OP_BEGIN_EVENT_RACE, event_id, car_id, 0, 0)) return 0;

    if (session_id) *session_id = (uint32_t)cmd.out0;
    return 1;
}

int __cdecl CampaignServiceCareerFinish(
    uint32_t session_id,
    int32_t position,
    int32_t stars,
    int32_t finish_time_ms,
    CampaignRaceResult* out
) {
    CampaignCommand cmd;

    if (!out || out->size < (uint32_t)sizeof(*out)) return 0;
    if (position <= 0 || stars < 0 || finish_time_ms < 0) return 0;

    out->session_id = session_id;
    out->credits_awarded = 0;
    out->premium_awarded = 0;
    out->stars_awarded = 0;
    out->revision = 0;

    if (!Run(
            &cmd,
            CAMPAIGN_OP_FINISH_EVENT_RACE,
            (int32_t)session_id,
            position,
            stars,
            finish_time_ms)) return 0;

    out->credits_awarded = cmd.out0;
    out->premium_awarded = cmd.out1;
    out->stars_awarded = stars;
    out->revision = cmd.revision;

    Publish(CAMPAIGN_EVENT_RACE_COMPLETED, stars, cmd.out0, cmd.out1, position);
    return 1;
}

int __cdecl CampaignServiceUpgradeApply(
    int32_t car_id,
    int32_t action_id,
    CampaignUpgradeResult* out
) {
    CampaignCommand cmd;

    if (car_id <= 0 || action_id <= 0 || !out || out->size < (uint32_t)sizeof(*out)) return 0;

    out->car_id = car_id;
    out->action_id = action_id;
    out->target_level = 0;
    out->balance_before = 0;
    out->balance_after = 0;
    out->revision = 0;

    if (!Run(&cmd, CAMPAIGN_OP_APPLY_UPGRADE_UI, car_id, action_id, 0, 0)) return 0;

    out->target_level = cmd.out0;
    out->balance_before = cmd.out1;
    out->balance_after = cmd.out2;
    out->revision = cmd.revision;

    Publish(CAMPAIGN_EVENT_UPGRADE_CHANGED, car_id, action_id, cmd.out0, cmd.out2);
    return 1;
}

int __cdecl CampaignServiceStorePurchase(int32_t offer_id, CampaignStoreResult* out) {
    CampaignCommand cmd;

    if (offer_id <= 0 || !out || out->size < (uint32_t)sizeof(*out)) return 0;

    out->offer_id = offer_id;
    out->item_id = 0;
    out->balance_before = 0;
    out->balance_after = 0;
    out->revision = 0;

    if (!Run(&cmd, CAMPAIGN_OP_PURCHASE_OFFER, offer_id, 0, 0, 0)) return 0;

    out->item_id = cmd.out0;
    out->balance_before = cmd.out1;
    out->balance_after = cmd.out2;
    out->revision = cmd.revision;

    Publish(CAMPAIGN_EVENT_STORE_CHANGED, offer_id, cmd.out0, cmd.out1, cmd.out2);
    return 1;
}
