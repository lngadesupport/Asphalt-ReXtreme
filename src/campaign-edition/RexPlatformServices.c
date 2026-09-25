#include "RexPlatformServices.h"

#include <limits.h>
#include <string.h>

static int RexPlatform_Copy(
    char* target,
    size_t target_size,
    const char* source
) {
    if (target == 0 || target_size == 0u ||
        source == 0) {
        return 0;
    }

    return strcpy_s(target, target_size, source) == 0;
}

int RexPlatformServices_Init(
    RexPlatformServices* services,
    const RexGaia* gaia
) {
    RexGaiaSession session = {0};

    if (services == 0 ||
        gaia == 0 ||
        !RexGaia_GetSession(gaia, &session)) {
        return 0;
    }

    memset(services, 0, sizeof(*services));

    if (!RexPlatform_Copy(
            services->profile.snapshot.profile_id,
            sizeof(services->profile.snapshot.profile_id),
            session.profile_id) ||
        !RexPlatform_Copy(
            services->login.profile_id,
            sizeof(services->login.profile_id),
            session.profile_id) ||
        !RexPlatform_Copy(
            services->version.snapshot.current_version,
            sizeof(services->version.snapshot.current_version),
            "1.7.3.8-campaign")) {
        memset(services, 0, sizeof(*services));
        return 0;
    }

    services->profile.snapshot.ready = 1;
    services->profile.snapshot.first_run_complete = 1;
    services->profile.snapshot.cloud_enabled = 0;

    services->connectivity.network_required = 0;
    services->connectivity.online = 0;

    services->login.authenticated = session.authenticated != 0;

    services->license.snapshot.active = 1;
    services->license.snapshot.trial = 0;
    services->license.snapshot.premium_campaign = 1;

    services->iap.enabled = 0;
    services->ads.enabled = 0;
    services->social.enabled = 0;
    services->matchmaking.enabled = 0;
    services->events.online_enabled = 0;
    services->remote_config.initialized = 1;

    services->version.snapshot.update_required = 0;
    services->version.snapshot.remote_check_enabled = 0;

    services->progression.snapshot.level = 1u;
    services->progression.snapshot.xp = 0u;

    services->initialized = 1;
    return 1;
}

int RexPlatformServices_GetCapabilities(
    const RexPlatformServices* services,
    RexPlatformCapabilities* capabilities
) {
    if (services == 0 ||
        capabilities == 0 ||
        !services->initialized) {
        return 0;
    }

    memset(capabilities, 0, sizeof(*capabilities));
    capabilities->profile_ready =
        services->profile.snapshot.ready;
    capabilities->cloud_sync_enabled =
        services->profile.snapshot.cloud_enabled;
    capabilities->network_required =
        services->connectivity.network_required;
    capabilities->login_authenticated =
        services->login.authenticated;
    capabilities->license_active =
        services->license.snapshot.active;
    capabilities->iap_enabled =
        services->iap.enabled;
    capabilities->ads_enabled =
        services->ads.enabled;
    capabilities->social_enabled =
        services->social.enabled;
    capabilities->matchmaking_enabled =
        services->matchmaking.enabled;
    capabilities->online_events_enabled =
        services->events.online_enabled;
    capabilities->update_required =
        services->version.snapshot.update_required;
    return 1;
}

int RexProfile_GetSnapshot(
    const RexProfileService* profile,
    RexProfileSnapshot* snapshot
) {
    if (profile == 0 || snapshot == 0 ||
        !profile->snapshot.ready) {
        return 0;
    }

    *snapshot = profile->snapshot;
    return 1;
}

int RexRemoteConfig_GetBool(
    const RexRemoteConfigService* config,
    const char* key,
    int* value
) {
    if (config == 0 || key == 0 || value == 0 ||
        !config->initialized) {
        return 0;
    }

    if (strcmp(key, "network_required") == 0 ||
        strcmp(key, "ads_enabled") == 0 ||
        strcmp(key, "iap_enabled") == 0 ||
        strcmp(key, "cloud_sync_enabled") == 0 ||
        strcmp(key, "social_enabled") == 0 ||
        strcmp(key, "matchmaking_enabled") == 0 ||
        strcmp(key, "online_events_enabled") == 0 ||
        strcmp(key, "remote_update_enabled") == 0) {
        *value = 0;
        return 1;
    }

    if (strcmp(key, "campaign_mode") == 0 ||
        strcmp(key, "premium_license") == 0) {
        *value = 1;
        return 1;
    }

    return 0;
}

uint32_t RexMailbox_Count(
    const RexMailboxService* mailbox
) {
    return mailbox == 0 ? 0u : mailbox->count;
}

RexPlatformResult RexMailbox_PushLocal(
    RexMailboxService* mailbox,
    uint32_t id,
    const char* title,
    const char* body
) {
    RexMailboxMessage* message;

    if (mailbox == 0 || id == 0u ||
        title == 0 || body == 0) {
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    if (mailbox->count >= REX_PLATFORM_MAILBOX_MAX) {
        return REX_PLATFORM_CAPACITY;
    }

    message = &mailbox->messages[mailbox->count];
    memset(message, 0, sizeof(*message));

    if (!RexPlatform_Copy(
            message->title,
            sizeof(message->title),
            title) ||
        !RexPlatform_Copy(
            message->body,
            sizeof(message->body),
            body)) {
        memset(message, 0, sizeof(*message));
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    message->id = id;
    mailbox->count += 1u;
    return REX_PLATFORM_OK;
}

int RexMailbox_Get(
    const RexMailboxService* mailbox,
    uint32_t index,
    RexMailboxMessage* message
) {
    if (mailbox == 0 || message == 0 ||
        index >= mailbox->count) {
        return 0;
    }

    *message = mailbox->messages[index];
    return 1;
}

static RexLeaderboardEntry* RexLeaderboard_FindMutable(
    RexLeaderboardService* leaderboard,
    uint32_t board_id
) {
    uint32_t i;

    for (i = 0u; i < leaderboard->count; ++i) {
        if (leaderboard->entries[i].board_id == board_id) {
            return &leaderboard->entries[i];
        }
    }

    return 0;
}

RexPlatformResult RexLeaderboard_SubmitLocal(
    RexLeaderboardService* leaderboard,
    uint32_t board_id,
    uint64_t score
) {
    RexLeaderboardEntry* entry;

    if (leaderboard == 0 || board_id == 0u) {
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    entry = RexLeaderboard_FindMutable(
        leaderboard,
        board_id
    );

    if (entry == 0) {
        if (leaderboard->count >=
            REX_PLATFORM_LEADERBOARD_MAX) {
            return REX_PLATFORM_CAPACITY;
        }

        entry = &leaderboard->entries[
            leaderboard->count
        ];
        entry->board_id = board_id;
        entry->best_score = score;
        leaderboard->count += 1u;
        return REX_PLATFORM_OK;
    }

    if (score > entry->best_score) {
        entry->best_score = score;
    }

    return REX_PLATFORM_OK;
}

int RexLeaderboard_GetBestLocal(
    const RexLeaderboardService* leaderboard,
    uint32_t board_id,
    uint64_t* score
) {
    uint32_t i;

    if (leaderboard == 0 ||
        board_id == 0u ||
        score == 0) {
        return 0;
    }

    for (i = 0u; i < leaderboard->count; ++i) {
        if (leaderboard->entries[i].board_id == board_id) {
            *score = leaderboard->entries[i].best_score;
            return 1;
        }
    }

    return 0;
}

RexPlatformResult RexIap_BeginPurchase(
    RexIapService* iap,
    const char* sku
) {
    if (iap == 0 || sku == 0 || sku[0] == '\0') {
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    return iap->enabled ?
        REX_PLATFORM_OK :
        REX_PLATFORM_DISABLED;
}

RexPlatformResult RexAds_Request(
    RexAdsService* ads
) {
    if (ads == 0) {
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    return ads->enabled ?
        REX_PLATFORM_OK :
        REX_PLATFORM_DISABLED;
}

RexPlatformResult RexSocial_Login(
    RexSocialService* social
) {
    if (social == 0) {
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    return social->enabled ?
        REX_PLATFORM_OK :
        REX_PLATFORM_DISABLED;
}

RexPlatformResult RexMatchmaking_Start(
    RexMatchmakingService* matchmaking
) {
    if (matchmaking == 0) {
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    return matchmaking->enabled ?
        REX_PLATFORM_OK :
        REX_PLATFORM_DISABLED;
}

RexPlatformResult RexEvents_RefreshOnline(
    RexEventsService* events
) {
    if (events == 0) {
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    return events->online_enabled ?
        REX_PLATFORM_OK :
        REX_PLATFORM_DISABLED;
}

int RexLicense_GetSnapshot(
    const RexLicenseService* license,
    RexLicenseSnapshot* snapshot
) {
    if (license == 0 || snapshot == 0) {
        return 0;
    }

    *snapshot = license->snapshot;
    return 1;
}

int RexVersion_GetSnapshot(
    const RexVersionService* version,
    RexVersionSnapshot* snapshot
) {
    if (version == 0 || snapshot == 0 ||
        version->snapshot.current_version[0] == '\0') {
        return 0;
    }

    *snapshot = version->snapshot;
    return 1;
}

static RexEconomyBalance* RexEconomy_FindMutable(
    RexEconomyService* economy,
    uint32_t currency_id
) {
    uint32_t i;

    for (i = 0u; i < economy->count; ++i) {
        if (economy->balances[i].currency_id ==
            currency_id) {
            return &economy->balances[i];
        }
    }

    return 0;
}

RexPlatformResult RexEconomy_SetBalance(
    RexEconomyService* economy,
    uint32_t currency_id,
    uint64_t amount
) {
    RexEconomyBalance* balance;

    if (economy == 0 || currency_id == 0u) {
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    balance = RexEconomy_FindMutable(
        economy,
        currency_id
    );

    if (balance == 0) {
        if (economy->count >= REX_PLATFORM_ECONOMY_MAX) {
            return REX_PLATFORM_CAPACITY;
        }

        balance = &economy->balances[economy->count];
        balance->currency_id = currency_id;
        economy->count += 1u;
    }

    balance->amount = amount;
    return REX_PLATFORM_OK;
}

RexPlatformResult RexEconomy_Credit(
    RexEconomyService* economy,
    uint32_t currency_id,
    uint64_t amount
) {
    RexEconomyBalance* balance;

    if (economy == 0 || currency_id == 0u) {
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    balance = RexEconomy_FindMutable(
        economy,
        currency_id
    );

    if (balance == 0) {
        return RexEconomy_SetBalance(
            economy,
            currency_id,
            amount
        );
    }

    if (UINT64_MAX - balance->amount < amount) {
        return REX_PLATFORM_OVERFLOW;
    }

    balance->amount += amount;
    return REX_PLATFORM_OK;
}

RexPlatformResult RexEconomy_Debit(
    RexEconomyService* economy,
    uint32_t currency_id,
    uint64_t amount
) {
    RexEconomyBalance* balance;

    if (economy == 0 || currency_id == 0u) {
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    balance = RexEconomy_FindMutable(
        economy,
        currency_id
    );

    if (balance == 0 ||
        balance->amount < amount) {
        return REX_PLATFORM_INSUFFICIENT;
    }

    balance->amount -= amount;
    return REX_PLATFORM_OK;
}

int RexEconomy_GetBalance(
    const RexEconomyService* economy,
    uint32_t currency_id,
    uint64_t* amount
) {
    uint32_t i;

    if (economy == 0 || currency_id == 0u ||
        amount == 0) {
        return 0;
    }

    for (i = 0u; i < economy->count; ++i) {
        if (economy->balances[i].currency_id ==
            currency_id) {
            *amount = economy->balances[i].amount;
            return 1;
        }
    }

    return 0;
}

static RexInventoryEntry* RexInventory_FindMutable(
    RexInventoryService* inventory,
    uint32_t item_id
) {
    uint32_t i;

    for (i = 0u; i < inventory->count; ++i) {
        if (inventory->entries[i].item_id == item_id) {
            return &inventory->entries[i];
        }
    }

    return 0;
}

RexPlatformResult RexInventory_SetAmount(
    RexInventoryService* inventory,
    uint32_t item_id,
    uint32_t amount
) {
    RexInventoryEntry* entry;

    if (inventory == 0 || item_id == 0u) {
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    entry = RexInventory_FindMutable(
        inventory,
        item_id
    );

    if (entry == 0) {
        if (inventory->count >= REX_PLATFORM_INVENTORY_MAX) {
            return REX_PLATFORM_CAPACITY;
        }

        entry = &inventory->entries[inventory->count];
        entry->item_id = item_id;
        inventory->count += 1u;
    }

    entry->amount = amount;
    return REX_PLATFORM_OK;
}

RexPlatformResult RexInventory_Add(
    RexInventoryService* inventory,
    uint32_t item_id,
    uint32_t amount
) {
    RexInventoryEntry* entry;

    if (inventory == 0 || item_id == 0u) {
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    entry = RexInventory_FindMutable(
        inventory,
        item_id
    );

    if (entry == 0) {
        return RexInventory_SetAmount(
            inventory,
            item_id,
            amount
        );
    }

    if (UINT_MAX - entry->amount < amount) {
        return REX_PLATFORM_OVERFLOW;
    }

    entry->amount += amount;
    return REX_PLATFORM_OK;
}

int RexInventory_GetAmount(
    const RexInventoryService* inventory,
    uint32_t item_id,
    uint32_t* amount
) {
    uint32_t i;

    if (inventory == 0 || item_id == 0u ||
        amount == 0) {
        return 0;
    }

    for (i = 0u; i < inventory->count; ++i) {
        if (inventory->entries[i].item_id == item_id) {
            *amount = inventory->entries[i].amount;
            return 1;
        }
    }

    return 0;
}

RexPlatformResult RexProgression_Set(
    RexProgressionService* progression,
    uint32_t level,
    uint64_t xp
) {
    if (progression == 0 || level == 0u) {
        return REX_PLATFORM_INVALID_ARGUMENT;
    }

    progression->snapshot.level = level;
    progression->snapshot.xp = xp;
    return REX_PLATFORM_OK;
}

int RexProgression_Get(
    const RexProgressionService* progression,
    RexProgressionSnapshot* snapshot
) {
    if (progression == 0 || snapshot == 0 ||
        progression->snapshot.level == 0u) {
        return 0;
    }

    *snapshot = progression->snapshot;
    return 1;
}
