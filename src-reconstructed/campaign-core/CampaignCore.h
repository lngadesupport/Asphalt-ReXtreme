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
    CAMPAIGN_OP_RELOAD = 91,
    CAMPAIGN_OP_DIAGNOSTICS = 92,
    CAMPAIGN_OP_GET_PROFILE_SUMMARY = 93,

    CAMPAIGN_OP_CHALLENGE_COUNT = 100,
    CAMPAIGN_OP_CHALLENGE_ID_AT = 101,
    CAMPAIGN_OP_CHALLENGE_STATUS = 102,
    CAMPAIGN_OP_CHALLENGE_REWARD = 103,
    CAMPAIGN_OP_CHALLENGE_ITEM_REWARD = 104,
    CAMPAIGN_OP_CHALLENGE_REFRESH = 105,
    CAMPAIGN_OP_CHALLENGE_CLAIM = 106,

    CAMPAIGN_OP_GET_STATISTICS = 110,

    CAMPAIGN_OP_ACHIEVEMENT_COUNT = 120,
    CAMPAIGN_OP_ACHIEVEMENT_ID_AT = 121,
    CAMPAIGN_OP_ACHIEVEMENT_STATUS = 122,
    CAMPAIGN_OP_ACHIEVEMENT_UNLOCK_DAY = 123,
    CAMPAIGN_OP_ACHIEVEMENT_REFRESH = 124,

    CAMPAIGN_OP_GET_LAST_RESULT = 130
};

enum CampaignStatisticsQuery {
    CAMPAIGN_STATISTICS_RACES = 0,
    CAMPAIGN_STATISTICS_MOVEMENT = 1,
    CAMPAIGN_STATISTICS_DESTRUCTION = 2,
    CAMPAIGN_STATISTICS_STUNTS = 3,
    CAMPAIGN_STATISTICS_NITRO = 4,
    CAMPAIGN_STATISTICS_BEST = 5
};

enum CampaignLastResultQuery {
    CAMPAIGN_LAST_RESULT_IDENTITY = 0,
    CAMPAIGN_LAST_RESULT_RACE = 1,
    CAMPAIGN_LAST_RESULT_REWARDS = 2,
    CAMPAIGN_LAST_RESULT_OBJECTIVES = 3,
    CAMPAIGN_LAST_RESULT_MOVEMENT = 4,
    CAMPAIGN_LAST_RESULT_DESTRUCTION = 5,
    CAMPAIGN_LAST_RESULT_STUNTS = 6,
    CAMPAIGN_LAST_RESULT_NITRO = 7
};

enum CampaignProfileSummaryQuery {
    CAMPAIGN_PROFILE_SUMMARY_PROGRESS = 0,
    CAMPAIGN_PROFILE_SUMMARY_ECONOMY = 1,
    CAMPAIGN_PROFILE_SUMMARY_GARAGE = 2
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

#define CAMPAIGN_UPGRADE_BATCH_MAX 16u

typedef struct CampaignUpgradeBatchArgs {
    uint32_t size;
    int32_t car_id;
    uint32_t count;
    int32_t ui_action_ids[CAMPAIGN_UPGRADE_BATCH_MAX];

    int32_t status;
    int32_t applied_count;
    uint32_t revision;
} CampaignUpgradeBatchArgs;

typedef struct CampaignRaceBeginArgs {
    int32_t event_id;
    int32_t car_id;
} CampaignRaceBeginArgs;

typedef struct CampaignRaceFinishArgs {
    int32_t position;
    int32_t stars;
    int32_t finish_time_ms;
} CampaignRaceFinishArgs;

int __cdecl CampaignBeginRaceAdapter(const CampaignRaceBeginArgs* args);
int __cdecl CampaignFinishRaceAdapter(const CampaignRaceFinishArgs* args);

int __cdecl CampaignApplyUpgradeBatch(CampaignUpgradeBatchArgs* args);
int __cdecl CampaignExecuteCommand(CampaignCommand* command);
int __cdecl CampaignIsOwned(int32_t car_id);
int __cdecl CampaignCraftInvoke(void* garage);

/* Thin read-only adapters for the preserved race engine/UI boundary. */
int __cdecl CampaignBeginRaceFromGui(void* game_mode_gui);
int __cdecl CampaignFinishRaceFromGui(void* game_mode_gui);

/*
  Per-frame Replay ABI. This remains fail-closed until the exact original
  GameModeGUIBase update/vehicle transform chain is verified for 1.7.3.8.
*/
int __cdecl CampaignReplayFrameFromGui(void* game_mode_gui);

/*
  Per-frame Photo Mode ABI. Remains fail-closed until the original camera/HUD
  chain is verified for 1.7.3.8.
*/
int __cdecl CampaignPhotoFrameFromGui(void* game_mode_gui);
int __cdecl CampaignPhotoToggleFromGui(void* game_mode_gui);

#ifdef __cplusplus
}
#endif
