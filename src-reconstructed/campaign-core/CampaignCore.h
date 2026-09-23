#pragma once
#include <stdint.h>
#include "CampaignObjectiveCatalog.h"

#ifdef __cplusplus
extern "C" {
#endif

enum CampaignCommandOp {
    CAMPAIGN_OP_NONE = 0,

    CAMPAIGN_OP_GET_CREDITS = 1,
    CAMPAIGN_OP_ADD_CREDITS = 2,
    CAMPAIGN_OP_SPEND_CREDITS = 3,

    CAMPAIGN_OP_GET_PREMIUM = 10,
    CAMPAIGN_OP_ADD_PREMIUM = 11,
    CAMPAIGN_OP_SPEND_PREMIUM = 12,

    CAMPAIGN_OP_INVENTORY_GET = 20,
    CAMPAIGN_OP_INVENTORY_ADD = 21,
    CAMPAIGN_OP_INVENTORY_SPEND = 22,

    CAMPAIGN_OP_IS_OWNED = 30,
    CAMPAIGN_OP_ACQUIRE_CAR = 31,
    CAMPAIGN_OP_CRAFT_CAR = 32,
    CAMPAIGN_OP_ACQUIRE_CATALOG = 33,

    CAMPAIGN_OP_GET_UPGRADE = 40,
    CAMPAIGN_OP_SET_UPGRADE = 41,
    CAMPAIGN_OP_APPLY_UPGRADE = 42,
    CAMPAIGN_OP_APPLY_UPGRADE_UI = 43,

    CAMPAIGN_OP_GET_PROKIT = 50,
    CAMPAIGN_OP_SET_PROKIT = 51,
    CAMPAIGN_OP_APPLY_PROKIT = 52,

    CAMPAIGN_OP_GET_PROGRESS = 60,
    CAMPAIGN_OP_SET_PROGRESS = 61,

    CAMPAIGN_OP_RECORD_RACE = 70,
    CAMPAIGN_OP_RECORD_EVENT = 71,
    CAMPAIGN_OP_BEGIN_EVENT_RACE = 72,
    CAMPAIGN_OP_FINISH_EVENT_RACE = 73,
    CAMPAIGN_OP_CANCEL_EVENT_RACE = 74,
    CAMPAIGN_OP_FINISH_EVENT_RACE_METRICS = 75,

    CAMPAIGN_OP_PURCHASE_OFFER = 80,

    CAMPAIGN_OP_SAVE = 90,
    CAMPAIGN_OP_RELOAD = 91
};

typedef struct CampaignCommand {
    uint32_t size;
    uint32_t op;
    int32_t a;
    int32_t b;
    int32_t c;
    int32_t d;

    int32_t status;
    int32_t out0;
    int32_t out1;
    int32_t out2;
    uint32_t revision;
} CampaignCommand;

int __cdecl CampaignExecuteCommand(CampaignCommand* command);
int __cdecl CampaignIsOwned(int32_t car_id);
int __cdecl CampaignCraftInvoke(void* garage);

#ifdef __cplusplus
}
#endif
