#pragma once

#include <stdint.h>

#include "RexGaia.h"

#ifdef __cplusplus
extern "C" {
#endif

#define REX_PLATFORM_PROFILE_ID_MAX 64u
#define REX_PLATFORM_MAILBOX_MAX 32u
#define REX_PLATFORM_MAIL_TITLE_MAX 64u
#define REX_PLATFORM_MAIL_BODY_MAX 256u
#define REX_PLATFORM_LEADERBOARD_MAX 64u
#define REX_PLATFORM_ECONOMY_MAX 16u
#define REX_PLATFORM_INVENTORY_MAX 256u

typedef enum RexPlatformResult {
    REX_PLATFORM_OK = 0,
    REX_PLATFORM_DISABLED = 1,
    REX_PLATFORM_INVALID_ARGUMENT = 2,
    REX_PLATFORM_NOT_FOUND = 3,
    REX_PLATFORM_CAPACITY = 4,
    REX_PLATFORM_INSUFFICIENT = 5,
    REX_PLATFORM_OVERFLOW = 6
} RexPlatformResult;

typedef struct RexPlatformCapabilities {
    int profile_ready;
    int cloud_sync_enabled;
    int network_required;
    int login_authenticated;
    int license_active;
    int iap_enabled;
    int ads_enabled;
    int social_enabled;
    int matchmaking_enabled;
    int online_events_enabled;
    int update_required;
} RexPlatformCapabilities;

typedef struct RexProfileSnapshot {
    char profile_id[REX_PLATFORM_PROFILE_ID_MAX];
    int ready;
    int first_run_complete;
    int cloud_enabled;
} RexProfileSnapshot;

typedef struct RexProfileService {
    RexProfileSnapshot snapshot;
} RexProfileService;

typedef struct RexConnectivityService {
    int network_required;
    int online;
} RexConnectivityService;

typedef struct RexLoginService {
    int authenticated;
    char profile_id[REX_PLATFORM_PROFILE_ID_MAX];
} RexLoginService;

typedef struct RexLicenseSnapshot {
    int active;
    int trial;
    int premium_campaign;
} RexLicenseSnapshot;

typedef struct RexLicenseService {
    RexLicenseSnapshot snapshot;
} RexLicenseService;

typedef struct RexIapService {
    int enabled;
} RexIapService;

typedef struct RexAdsService {
    int enabled;
} RexAdsService;

typedef struct RexSocialService {
    int enabled;
} RexSocialService;

typedef struct RexMailboxMessage {
    uint32_t id;
    char title[REX_PLATFORM_MAIL_TITLE_MAX];
    char body[REX_PLATFORM_MAIL_BODY_MAX];
    int read;
} RexMailboxMessage;

typedef struct RexMailboxService {
    RexMailboxMessage messages[REX_PLATFORM_MAILBOX_MAX];
    uint32_t count;
} RexMailboxService;

typedef struct RexLeaderboardEntry {
    uint32_t board_id;
    uint64_t best_score;
} RexLeaderboardEntry;

typedef struct RexLeaderboardService {
    RexLeaderboardEntry entries[REX_PLATFORM_LEADERBOARD_MAX];
    uint32_t count;
} RexLeaderboardService;

typedef struct RexMatchmakingService {
    int enabled;
} RexMatchmakingService;

typedef struct RexEventsService {
    int online_enabled;
} RexEventsService;

typedef struct RexRemoteConfigService {
    int initialized;
} RexRemoteConfigService;

typedef struct RexVersionSnapshot {
    char current_version[32];
    int update_required;
    int remote_check_enabled;
} RexVersionSnapshot;

typedef struct RexVersionService {
    RexVersionSnapshot snapshot;
} RexVersionService;

typedef struct RexEconomyBalance {
    uint32_t currency_id;
    uint64_t amount;
} RexEconomyBalance;

typedef struct RexEconomyService {
    RexEconomyBalance balances[REX_PLATFORM_ECONOMY_MAX];
    uint32_t count;
} RexEconomyService;

typedef struct RexInventoryEntry {
    uint32_t item_id;
    uint32_t amount;
} RexInventoryEntry;

typedef struct RexInventoryService {
    RexInventoryEntry entries[REX_PLATFORM_INVENTORY_MAX];
    uint32_t count;
} RexInventoryService;

typedef struct RexProgressionSnapshot {
    uint32_t level;
    uint64_t xp;
} RexProgressionSnapshot;

typedef struct RexProgressionService {
    RexProgressionSnapshot snapshot;
} RexProgressionService;

typedef struct RexPlatformServices {
    RexProfileService profile;
    RexConnectivityService connectivity;
    RexLoginService login;
    RexLicenseService license;
    RexIapService iap;
    RexAdsService ads;
    RexSocialService social;
    RexMailboxService mailbox;
    RexLeaderboardService leaderboard;
    RexMatchmakingService matchmaking;
    RexEventsService events;
    RexRemoteConfigService remote_config;
    RexVersionService version;
    RexEconomyService economy;
    RexInventoryService inventory;
    RexProgressionService progression;
    int initialized;
} RexPlatformServices;

int RexPlatformServices_Init(
    RexPlatformServices* services,
    const RexGaia* gaia
);

int RexPlatformServices_GetCapabilities(
    const RexPlatformServices* services,
    RexPlatformCapabilities* capabilities
);

int RexProfile_GetSnapshot(
    const RexProfileService* profile,
    RexProfileSnapshot* snapshot
);

int RexRemoteConfig_GetBool(
    const RexRemoteConfigService* config,
    const char* key,
    int* value
);

uint32_t RexMailbox_Count(
    const RexMailboxService* mailbox
);

RexPlatformResult RexMailbox_PushLocal(
    RexMailboxService* mailbox,
    uint32_t id,
    const char* title,
    const char* body
);

int RexMailbox_Get(
    const RexMailboxService* mailbox,
    uint32_t index,
    RexMailboxMessage* message
);

RexPlatformResult RexLeaderboard_SubmitLocal(
    RexLeaderboardService* leaderboard,
    uint32_t board_id,
    uint64_t score
);

int RexLeaderboard_GetBestLocal(
    const RexLeaderboardService* leaderboard,
    uint32_t board_id,
    uint64_t* score
);

RexPlatformResult RexIap_BeginPurchase(
    RexIapService* iap,
    const char* sku
);

RexPlatformResult RexAds_Request(
    RexAdsService* ads
);

RexPlatformResult RexSocial_Login(
    RexSocialService* social
);

RexPlatformResult RexMatchmaking_Start(
    RexMatchmakingService* matchmaking
);

RexPlatformResult RexEvents_RefreshOnline(
    RexEventsService* events
);

int RexLicense_GetSnapshot(
    const RexLicenseService* license,
    RexLicenseSnapshot* snapshot
);

int RexVersion_GetSnapshot(
    const RexVersionService* version,
    RexVersionSnapshot* snapshot
);

RexPlatformResult RexEconomy_SetBalance(
    RexEconomyService* economy,
    uint32_t currency_id,
    uint64_t amount
);

RexPlatformResult RexEconomy_Credit(
    RexEconomyService* economy,
    uint32_t currency_id,
    uint64_t amount
);

RexPlatformResult RexEconomy_Debit(
    RexEconomyService* economy,
    uint32_t currency_id,
    uint64_t amount
);

int RexEconomy_GetBalance(
    const RexEconomyService* economy,
    uint32_t currency_id,
    uint64_t* amount
);

RexPlatformResult RexInventory_SetAmount(
    RexInventoryService* inventory,
    uint32_t item_id,
    uint32_t amount
);

RexPlatformResult RexInventory_Add(
    RexInventoryService* inventory,
    uint32_t item_id,
    uint32_t amount
);

int RexInventory_GetAmount(
    const RexInventoryService* inventory,
    uint32_t item_id,
    uint32_t* amount
);

RexPlatformResult RexProgression_Set(
    RexProgressionService* progression,
    uint32_t level,
    uint64_t xp
);

int RexProgression_Get(
    const RexProgressionService* progression,
    RexProgressionSnapshot* snapshot
);

#ifdef __cplusplus
}
#endif
