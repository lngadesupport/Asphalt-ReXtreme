#include "RexPlatformServices.h"
#include "RexGaia.h"

#include <stdio.h>
#include <string.h>

static int failures = 0;

#define CHECK(expr) do { \
    if (!(expr)) { \
        printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #expr); \
        failures += 1; \
    } \
} while (0)

static void test_platform_bootstrap_replaces_remote_service_policy(void) {
    RexGaia gaia = {0};
    RexPlatformServices services = {0};
    RexPlatformCapabilities caps = {0};

    CHECK(RexGaia_Init(&gaia, "campaign-local") == 1);
    CHECK(RexPlatformServices_Init(&services, &gaia) == 1);
    CHECK(RexPlatformServices_GetCapabilities(&services, &caps) == 1);

    CHECK(caps.profile_ready == 1);
    CHECK(caps.cloud_sync_enabled == 0);
    CHECK(caps.network_required == 0);
    CHECK(caps.login_authenticated == 1);
    CHECK(caps.license_active == 1);
    CHECK(caps.iap_enabled == 0);
    CHECK(caps.ads_enabled == 0);
    CHECK(caps.social_enabled == 0);
    CHECK(caps.matchmaking_enabled == 0);
    CHECK(caps.online_events_enabled == 0);
    CHECK(caps.update_required == 0);
}

static void test_profile_is_local_and_first_run_is_complete(void) {
    RexGaia gaia = {0};
    RexPlatformServices services = {0};
    RexProfileSnapshot profile = {0};

    CHECK(RexGaia_Init(&gaia, "campaign-local") == 1);
    CHECK(RexPlatformServices_Init(&services, &gaia) == 1);
    CHECK(RexProfile_GetSnapshot(&services.profile, &profile) == 1);

    CHECK(strcmp(profile.profile_id, "campaign-local") == 0);
    CHECK(profile.ready == 1);
    CHECK(profile.first_run_complete == 1);
    CHECK(profile.cloud_enabled == 0);
}

static void test_remote_config_is_local_and_disables_remote_features(void) {
    RexGaia gaia = {0};
    RexPlatformServices services = {0};
    int value = -1;

    CHECK(RexGaia_Init(&gaia, "campaign-local") == 1);
    CHECK(RexPlatformServices_Init(&services, &gaia) == 1);

    CHECK(RexRemoteConfig_GetBool(
        &services.remote_config,
        "network_required",
        &value
    ) == 1);
    CHECK(value == 0);

    CHECK(RexRemoteConfig_GetBool(
        &services.remote_config,
        "ads_enabled",
        &value
    ) == 1);
    CHECK(value == 0);

    CHECK(RexRemoteConfig_GetBool(
        &services.remote_config,
        "iap_enabled",
        &value
    ) == 1);
    CHECK(value == 0);

    CHECK(RexRemoteConfig_GetBool(
        &services.remote_config,
        "cloud_sync_enabled",
        &value
    ) == 1);
    CHECK(value == 0);
}

static void test_mailbox_and_leaderboard_are_local(void) {
    RexGaia gaia = {0};
    RexPlatformServices services = {0};
    RexMailboxMessage message = {0};
    uint64_t best = 0u;

    CHECK(RexGaia_Init(&gaia, "campaign-local") == 1);
    CHECK(RexPlatformServices_Init(&services, &gaia) == 1);

    CHECK(RexMailbox_Count(&services.mailbox) == 0u);
    CHECK(RexMailbox_PushLocal(
        &services.mailbox,
        7u,
        "Campaign",
        "Local reward ready"
    ) == REX_PLATFORM_OK);
    CHECK(RexMailbox_Count(&services.mailbox) == 1u);
    CHECK(RexMailbox_Get(&services.mailbox, 0u, &message) == 1);
    CHECK(message.id == 7u);
    CHECK(strcmp(message.title, "Campaign") == 0);

    CHECK(RexLeaderboard_SubmitLocal(
        &services.leaderboard,
        10u,
        1200u
    ) == REX_PLATFORM_OK);
    CHECK(RexLeaderboard_SubmitLocal(
        &services.leaderboard,
        10u,
        900u
    ) == REX_PLATFORM_OK);
    CHECK(RexLeaderboard_GetBestLocal(
        &services.leaderboard,
        10u,
        &best
    ) == 1);
    CHECK(best == 1200u);
}

static void test_online_only_services_are_explicitly_disabled(void) {
    RexGaia gaia = {0};
    RexPlatformServices services = {0};

    CHECK(RexGaia_Init(&gaia, "campaign-local") == 1);
    CHECK(RexPlatformServices_Init(&services, &gaia) == 1);

    CHECK(RexIap_BeginPurchase(&services.iap, "anything") == REX_PLATFORM_DISABLED);
    CHECK(RexAds_Request(&services.ads) == REX_PLATFORM_DISABLED);
    CHECK(RexSocial_Login(&services.social) == REX_PLATFORM_DISABLED);
    CHECK(RexMatchmaking_Start(&services.matchmaking) == REX_PLATFORM_DISABLED);
    CHECK(RexEvents_RefreshOnline(&services.events) == REX_PLATFORM_DISABLED);
}

static void test_license_and_version_are_campaign_local(void) {
    RexGaia gaia = {0};
    RexPlatformServices services = {0};
    RexLicenseSnapshot license = {0};
    RexVersionSnapshot version = {0};

    CHECK(RexGaia_Init(&gaia, "campaign-local") == 1);
    CHECK(RexPlatformServices_Init(&services, &gaia) == 1);

    CHECK(RexLicense_GetSnapshot(&services.license, &license) == 1);
    CHECK(license.active == 1);
    CHECK(license.trial == 0);
    CHECK(license.premium_campaign == 1);

    CHECK(RexVersion_GetSnapshot(&services.version, &version) == 1);
    CHECK(strcmp(version.current_version, "1.7.3.8-campaign") == 0);
    CHECK(version.update_required == 0);
    CHECK(version.remote_check_enabled == 0);
}

static void test_economy_inventory_and_progression_are_local_state_engines(void) {
    RexGaia gaia = {0};
    RexPlatformServices services = {0};
    uint64_t balance = 0u;
    uint32_t amount = 0u;
    RexProgressionSnapshot progression = {0};

    CHECK(RexGaia_Init(&gaia, "campaign-local") == 1);
    CHECK(RexPlatformServices_Init(&services, &gaia) == 1);

    CHECK(RexEconomy_SetBalance(&services.economy, 1u, 500u) == REX_PLATFORM_OK);
    CHECK(RexEconomy_Credit(&services.economy, 1u, 50u) == REX_PLATFORM_OK);
    CHECK(RexEconomy_Debit(&services.economy, 1u, 125u) == REX_PLATFORM_OK);
    CHECK(RexEconomy_GetBalance(&services.economy, 1u, &balance) == 1);
    CHECK(balance == 425u);

    CHECK(RexInventory_SetAmount(&services.inventory, 99u, 3u) == REX_PLATFORM_OK);
    CHECK(RexInventory_Add(&services.inventory, 99u, 2u) == REX_PLATFORM_OK);
    CHECK(RexInventory_GetAmount(&services.inventory, 99u, &amount) == 1);
    CHECK(amount == 5u);

    CHECK(RexProgression_Set(
        &services.progression,
        8u,
        12345u
    ) == REX_PLATFORM_OK);
    CHECK(RexProgression_Get(
        &services.progression,
        &progression
    ) == 1);
    CHECK(progression.level == 8u);
    CHECK(progression.xp == 12345u);
}

int main(void) {
    test_platform_bootstrap_replaces_remote_service_policy();
    test_profile_is_local_and_first_run_is_complete();
    test_remote_config_is_local_and_disables_remote_features();
    test_mailbox_and_leaderboard_are_local();
    test_online_only_services_are_explicitly_disabled();
    test_license_and_version_are_campaign_local();
    test_economy_inventory_and_progression_are_local_state_engines();

    if (failures != 0) {
        printf("%d platform service assertion(s) failed.\n", failures);
        return 1;
    }

    printf("ReX platform services tests passed.\n");
    return 0;
}
