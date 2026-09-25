#include "RexHost.h"
#include "RexRuntime.h"

#include <string.h>

static RexRuntime g_rex_runtime;
static int g_rex_started = 0;

int RexHost_Start(
    const char* content_path,
    const char* state_path,
    const RexPresentationGaragePort* presentation_port
) {
    if (g_rex_started ||
        content_path == 0 ||
        state_path == 0 ||
        presentation_port == 0) {
        return 0;
    }

    if (!RexRuntime_Init(
            &g_rex_runtime,
            content_path,
            state_path,
            *presentation_port)) {
        return 0;
    }

    g_rex_started = 1;
    return 1;
}

int RexHost_IsStarted(void) {
    return g_rex_started;
}

int RexHost_GarageEnter(void) {
    if (!g_rex_started) {
        return 0;
    }

    return RexRuntime_OnGarageEnter(&g_rex_runtime);
}

int RexHost_GarageSelectionChanged(void) {
    if (!g_rex_started) {
        return 0;
    }

    return RexRuntime_OnGarageSelectionChanged(&g_rex_runtime);
}

int RexHost_GarageMontarPressed(void) {
    if (!g_rex_started) {
        return (int)REX_GARAGE_PRESENTER_READ_FAILED;
    }

    return (int)RexRuntime_OnGarageMontarPressed(
        &g_rex_runtime
    );
}

int RexHost_GaiaIsReady(void) {
    if (!g_rex_started) {
        return 0;
    }

    return RexGaia_IsReady(&g_rex_runtime.gaia);
}

int RexHost_GaiaIsNetworkRequired(void) {
    if (!g_rex_started) {
        return 1;
    }

    return RexGaia_IsNetworkRequired(&g_rex_runtime.gaia);
}

uint32_t RexHost_GlobalSyncPendingCount(void) {
    if (!g_rex_started) {
        return 0u;
    }

    return RexGlobalSync_GetPendingCount(
        &g_rex_runtime.global_sync
    );
}

int RexHost_GlobalSyncCommit(
    uint32_t reason,
    uint32_t* operation_id
) {
    if (!g_rex_started ||
        operation_id == 0 ||
        reason < (uint32_t)REX_GLOBAL_SYNC_REASON_PROFILE_BOOTSTRAP ||
        reason > (uint32_t)REX_GLOBAL_SYNC_REASON_CAREER) {
        return (int)REX_GLOBAL_SYNC_INVALID_ARGUMENT;
    }

    return (int)RexGlobalSync_Commit(
        &g_rex_runtime.global_sync,
        (RexGlobalSyncReason)reason,
        operation_id
    );
}

static uint64_t RexHost_PlatformCapabilityFlags(void) {
    RexPlatformCapabilities caps = {0};
    uint64_t flags = 0u;

    if (!RexPlatformServices_GetCapabilities(
            &g_rex_runtime.platform_services,
            &caps)) {
        return 0u;
    }

    if (caps.profile_ready) {
        flags |= REX_PLATFORM_FLAG_PROFILE_READY;
    }
    if (caps.cloud_sync_enabled) {
        flags |= REX_PLATFORM_FLAG_CLOUD_SYNC_ENABLED;
    }
    if (caps.network_required) {
        flags |= REX_PLATFORM_FLAG_NETWORK_REQUIRED;
    }
    if (caps.login_authenticated) {
        flags |= REX_PLATFORM_FLAG_LOGIN_AUTHENTICATED;
    }
    if (caps.license_active) {
        flags |= REX_PLATFORM_FLAG_LICENSE_ACTIVE;
    }
    if (caps.iap_enabled) {
        flags |= REX_PLATFORM_FLAG_IAP_ENABLED;
    }
    if (caps.ads_enabled) {
        flags |= REX_PLATFORM_FLAG_ADS_ENABLED;
    }
    if (caps.social_enabled) {
        flags |= REX_PLATFORM_FLAG_SOCIAL_ENABLED;
    }
    if (caps.matchmaking_enabled) {
        flags |= REX_PLATFORM_FLAG_MATCHMAKING_ENABLED;
    }
    if (caps.online_events_enabled) {
        flags |= REX_PLATFORM_FLAG_ONLINE_EVENTS_ENABLED;
    }
    if (caps.update_required) {
        flags |= REX_PLATFORM_FLAG_UPDATE_REQUIRED;
    }

    return flags;
}

int RexHost_PlatformDispatchV1(
    RexPlatformRequestV1* request
) {
    RexPlatformServices* services;
    RexGaiaSession gaia_session = {0};
    RexProfileSnapshot profile = {0};
    RexLicenseSnapshot license = {0};
    RexVersionSnapshot version = {0};
    RexProgressionSnapshot progression = {0};
    uint64_t amount64 = 0u;
    uint32_t amount32 = 0u;
    uint32_t operation_id = 0u;
    int bool_value = 0;

    if (!g_rex_started ||
        request == 0 ||
        request->abi_version != REX_PLATFORM_DISPATCH_ABI_VERSION ||
        request->struct_size < (uint32_t)sizeof(*request)) {
        return 0;
    }

    services = &g_rex_runtime.platform_services;
    request->status = REX_PLATFORM_INVALID_ARGUMENT;
    request->result = 0u;

    switch ((RexPlatformOpcodeV1)request->opcode) {
        case REX_PLATFORM_OP_GET_CAPABILITIES:
            request->result = RexHost_PlatformCapabilityFlags();
            request->status = REX_PLATFORM_OK;
            return 1;

        case REX_PLATFORM_OP_GAIA_STATUS:
            if (!RexGaia_GetSession(
                    &g_rex_runtime.gaia,
                    &gaia_session)) {
                return 1;
            }
            request->result =
                (RexGaia_IsReady(&g_rex_runtime.gaia) ? 1u : 0u) |
                (RexGaia_IsNetworkRequired(&g_rex_runtime.gaia) ? 2u : 0u);
            strcpy_s(
                request->text,
                sizeof(request->text),
                gaia_session.profile_id
            );
            request->status = REX_PLATFORM_OK;
            return 1;

        case REX_PLATFORM_OP_GLOBAL_SYNC_COMMIT:
            request->status = RexHost_GlobalSyncCommit(
                request->id,
                &operation_id
            );
            request->aux_u32 = operation_id;
            request->result = g_rex_runtime.state.revision;
            return 1;

        case REX_PLATFORM_OP_PROFILE_STATUS:
            if (!RexProfile_GetSnapshot(
                    &services->profile,
                    &profile)) {
                return 1;
            }
            request->result =
                (profile.ready ? 1u : 0u) |
                (profile.first_run_complete ? 2u : 0u) |
                (profile.cloud_enabled ? 4u : 0u);
            strcpy_s(
                request->text,
                sizeof(request->text),
                profile.profile_id
            );
            request->status = REX_PLATFORM_OK;
            return 1;

        case REX_PLATFORM_OP_CONNECTIVITY_STATUS:
            request->result =
                (services->connectivity.network_required ? 1u : 0u) |
                (services->connectivity.online ? 2u : 0u);
            request->status = REX_PLATFORM_OK;
            return 1;

        case REX_PLATFORM_OP_LOGIN_STATUS:
            request->result =
                services->login.authenticated ? 1u : 0u;
            strcpy_s(
                request->text,
                sizeof(request->text),
                services->login.profile_id
            );
            request->status = REX_PLATFORM_OK;
            return 1;

        case REX_PLATFORM_OP_LICENSE_STATUS:
            if (!RexLicense_GetSnapshot(
                    &services->license,
                    &license)) {
                return 1;
            }
            request->result =
                (license.active ? 1u : 0u) |
                (license.trial ? 2u : 0u) |
                (license.premium_campaign ? 4u : 0u);
            request->status = REX_PLATFORM_OK;
            return 1;

        case REX_PLATFORM_OP_REMOTE_CONFIG_BOOL:
            if (!RexRemoteConfig_GetBool(
                    &services->remote_config,
                    request->text,
                    &bool_value)) {
                request->status = REX_PLATFORM_NOT_FOUND;
                return 1;
            }
            request->result = bool_value ? 1u : 0u;
            request->status = REX_PLATFORM_OK;
            return 1;

        case REX_PLATFORM_OP_MAILBOX_COUNT:
            request->result = RexMailbox_Count(
                &services->mailbox
            );
            request->status = REX_PLATFORM_OK;
            return 1;

        case REX_PLATFORM_OP_LEADERBOARD_SUBMIT:
            request->status = RexLeaderboard_SubmitLocal(
                &services->leaderboard,
                request->id,
                request->value
            );
            return 1;

        case REX_PLATFORM_OP_LEADERBOARD_GET:
            if (!RexLeaderboard_GetBestLocal(
                    &services->leaderboard,
                    request->id,
                    &amount64)) {
                request->status = REX_PLATFORM_NOT_FOUND;
                return 1;
            }
            request->result = amount64;
            request->status = REX_PLATFORM_OK;
            return 1;

        case REX_PLATFORM_OP_ECONOMY_SET:
            request->status = RexEconomy_SetBalance(
                &services->economy,
                request->id,
                request->value
            );
            return 1;

        case REX_PLATFORM_OP_ECONOMY_CREDIT:
            request->status = RexEconomy_Credit(
                &services->economy,
                request->id,
                request->value
            );
            return 1;

        case REX_PLATFORM_OP_ECONOMY_DEBIT:
            request->status = RexEconomy_Debit(
                &services->economy,
                request->id,
                request->value
            );
            return 1;

        case REX_PLATFORM_OP_ECONOMY_GET:
            if (!RexEconomy_GetBalance(
                    &services->economy,
                    request->id,
                    &amount64)) {
                request->status = REX_PLATFORM_NOT_FOUND;
                return 1;
            }
            request->result = amount64;
            request->status = REX_PLATFORM_OK;
            return 1;

        case REX_PLATFORM_OP_IAP_PURCHASE:
            request->status = RexIap_BeginPurchase(
                &services->iap,
                request->text
            );
            return 1;

        case REX_PLATFORM_OP_ADS_REQUEST:
            request->status = RexAds_Request(
                &services->ads
            );
            return 1;

        case REX_PLATFORM_OP_SOCIAL_LOGIN:
            request->status = RexSocial_Login(
                &services->social
            );
            return 1;

        case REX_PLATFORM_OP_MATCHMAKING_START:
            request->status = RexMatchmaking_Start(
                &services->matchmaking
            );
            return 1;

        case REX_PLATFORM_OP_EVENTS_REFRESH:
            request->status = RexEvents_RefreshOnline(
                &services->events
            );
            return 1;

        case REX_PLATFORM_OP_INVENTORY_SET:
            request->status = RexInventory_SetAmount(
                &services->inventory,
                request->id,
                request->aux_u32
            );
            return 1;

        case REX_PLATFORM_OP_INVENTORY_ADD:
            request->status = RexInventory_Add(
                &services->inventory,
                request->id,
                request->aux_u32
            );
            return 1;

        case REX_PLATFORM_OP_INVENTORY_GET:
            if (!RexInventory_GetAmount(
                    &services->inventory,
                    request->id,
                    &amount32)) {
                request->status = REX_PLATFORM_NOT_FOUND;
                return 1;
            }
            request->aux_u32 = amount32;
            request->status = REX_PLATFORM_OK;
            return 1;

        case REX_PLATFORM_OP_PROGRESSION_SET:
            request->status = RexProgression_Set(
                &services->progression,
                request->aux_u32,
                request->value
            );
            return 1;

        case REX_PLATFORM_OP_PROGRESSION_GET:
            if (!RexProgression_Get(
                    &services->progression,
                    &progression)) {
                return 1;
            }
            request->aux_u32 = progression.level;
            request->result = progression.xp;
            request->status = REX_PLATFORM_OK;
            return 1;

        case REX_PLATFORM_OP_VERSION_STATUS:
            if (!RexVersion_GetSnapshot(
                    &services->version,
                    &version)) {
                return 1;
            }
            request->result =
                (version.update_required ? 1u : 0u) |
                (version.remote_check_enabled ? 2u : 0u);
            strcpy_s(
                request->text,
                sizeof(request->text),
                version.current_version
            );
            request->status = REX_PLATFORM_OK;
            return 1;

        default:
            return 0;
    }
}
