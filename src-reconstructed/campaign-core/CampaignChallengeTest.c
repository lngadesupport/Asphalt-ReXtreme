#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignChallengeCatalog.h"

typedef struct TestChallengeCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignChallengeDefinition entries[CAMPAIGN_CHALLENGE_MAX];
    uint32_t checksum;
} TestChallengeCatalogFile;

static TestChallengeCatalogFile g_test_catalog;

static uint32_t TestHash(const void* p, uint32_t n) {
    const unsigned char* s = (const unsigned char*)p;
    uint32_t h = 2166136261u;
    uint32_t i;
    for (i = 0; i < n; ++i) {
        h ^= s[i];
        h *= 16777619u;
    }
    return h;
}

static int WriteCatalog(void) {
    const WCHAR* path = L"prebuilt\\campaign-core\\CampaignChallenges.dat";
    HANDLE h;
    DWORD written = 0;

    ZeroMemory(&g_test_catalog, sizeof(g_test_catalog));
    g_test_catalog.magic = CAMPAIGN_CHALLENGE_CATALOG_MAGIC;
    g_test_catalog.version = CAMPAIGN_CHALLENGE_CATALOG_VERSION;
    g_test_catalog.count = 4;

    g_test_catalog.entries[0].challenge_id = 1;
    g_test_catalog.entries[0].scope = CAMPAIGN_CHALLENGE_DAILY;
    g_test_catalog.entries[0].metric = CAMPAIGN_METRIC_DRIFT_METERS;
    g_test_catalog.entries[0].progress_mode = CAMPAIGN_CHALLENGE_SUM_METRIC;
    g_test_catalog.entries[0].goal = 1000;
    g_test_catalog.entries[0].reward_credits = 500;

    g_test_catalog.entries[1].challenge_id = 2;
    g_test_catalog.entries[1].scope = CAMPAIGN_CHALLENGE_WEEKLY;
    g_test_catalog.entries[1].metric = CAMPAIGN_METRIC_PLACEMENT;
    g_test_catalog.entries[1].progress_mode = CAMPAIGN_CHALLENGE_COUNT_MATCHES;
    g_test_catalog.entries[1].goal = 2;
    g_test_catalog.entries[1].qualifier_compare = CAMPAIGN_COMPARE_LE;
    g_test_catalog.entries[1].qualifier_threshold = 1;
    g_test_catalog.entries[1].reward_premium = 3;

    g_test_catalog.entries[2].challenge_id = 3;
    g_test_catalog.entries[2].scope = CAMPAIGN_CHALLENGE_PERMANENT;
    g_test_catalog.entries[2].metric = CAMPAIGN_METRIC_AIR_TIME_MS;
    g_test_catalog.entries[2].progress_mode = CAMPAIGN_CHALLENGE_BEST_MAX;
    g_test_catalog.entries[2].goal = 5000;
    g_test_catalog.entries[2].reward_item_id = 2001;
    g_test_catalog.entries[2].reward_item_amount = 1;

    g_test_catalog.entries[3].challenge_id = 4;
    g_test_catalog.entries[3].scope = CAMPAIGN_CHALLENGE_PERMANENT;
    g_test_catalog.entries[3].metric = CAMPAIGN_METRIC_FINISH_TIME_MS;
    g_test_catalog.entries[3].progress_mode = CAMPAIGN_CHALLENGE_BEST_MIN;
    g_test_catalog.entries[3].goal = 60000;

    g_test_catalog.checksum = TestHash(
        &g_test_catalog,
        (uint32_t)sizeof(g_test_catalog) - (uint32_t)sizeof(uint32_t)
    );

    h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;
    if (!WriteFile(h, &g_test_catalog, (DWORD)sizeof(g_test_catalog), &written, 0) ||
        written != (DWORD)sizeof(g_test_catalog)) {
        CloseHandle(h);
        return 0;
    }
    CloseHandle(h);
    return 1;
}

static int Status(int32_t id, CampaignChallengeStatus* out) {
    ZeroMemory(out, sizeof(*out));
    out->size = sizeof(*out);
    return CampaignChallengesGetStatus(id, out);
}

int main(void) {
    CampaignRaceMetrics metrics;
    CampaignChallengeStatus s;

    DeleteFileW(L"prebuilt\\campaign-core\\CampaignChallenges.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\UserData\\CampaignEdition\\ChallengeState.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\UserData\\CampaignEdition\\ChallengeState.tmp");

    if (!WriteCatalog()) return 10;
    if (!CampaignChallengeCatalogEnsureLoaded()) return 11;
    if (CampaignChallengeCatalogCount() != 4) return 12;
    if (!CampaignChallengesEnsureLoaded()) return 13;

    ZeroMemory(&metrics, sizeof(metrics));
    metrics.size = sizeof(metrics);
    metrics.version = CAMPAIGN_RACE_METRICS_VERSION;
    metrics.placement = 1;
    metrics.finish_time_ms = 65000;
    metrics.drift_meters = 600;
    metrics.air_time_ms = 4000;

    if (!CampaignChallengesOnRace(42, &metrics)) return 20;
    if (!Status(1, &s) || s.progress != 600 || s.completed) return 21;
    if (!Status(2, &s) || s.progress != 1 || s.completed) return 22;
    if (!Status(3, &s) || s.progress != 4000 || s.completed) return 23;
    if (!Status(4, &s) || s.progress != 65000 || s.completed) return 24;

    metrics.finish_time_ms = 59000;
    metrics.drift_meters = 500;
    metrics.air_time_ms = 5500;
    if (!CampaignChallengesOnRace(42, &metrics)) return 30;

    if (!Status(1, &s) || s.progress != 1100 || !s.completed ||
        s.reward_credits != 500) return 31;
    if (!Status(2, &s) || s.progress != 2 || !s.completed ||
        s.reward_premium != 3) return 32;
    if (!Status(3, &s) || s.progress != 5500 || !s.completed ||
        s.reward_item_id != 2001 || s.reward_item_amount != 1) return 33;
    if (!Status(4, &s) || s.progress != 59000 || !s.completed) return 34;

    if (!CampaignChallengesCanClaim(1, &s) || s.claimed) return 35;
    {
        CampaignChallengeClaim claim;
        CampaignChallengeClaim pending;
        ZeroMemory(&claim, sizeof(claim));
        ZeroMemory(&pending, sizeof(pending));
        claim.size = sizeof(claim);
        pending.size = sizeof(pending);

        if (!CampaignChallengesBeginClaim(1, 10, &claim)) return 36;
        if (claim.challenge_id != 1 ||
            claim.start_campaign_revision != 10 ||
            claim.reward_credits != 500) return 37;
        if (!CampaignChallengesGetPendingClaim(&pending) ||
            pending.challenge_id != 1) return 38;

        /* Non-zero reward cannot finalize before Campaign revision advances. */
        if (CampaignChallengesFinalizeClaim(1, 10)) return 39;
        if (!CampaignChallengesFinalizeClaim(1, 11)) return 40;
        if (!Status(1, &s) || !s.claimed || CampaignChallengesCanClaim(1, 0)) return 41;
    }

    /* Recovery path: revision advance finalizes pending claim without regrant. */
    {
        CampaignChallengeClaim claim;
        ZeroMemory(&claim, sizeof(claim));
        claim.size = sizeof(claim);
        if (!CampaignChallengesBeginClaim(2, 20, &claim)) return 42;
        if (!CampaignChallengesRecoverClaim(20)) return 43;
        if (!Status(2, &s) || s.claimed) return 44;
        if (!CampaignChallengesRecoverClaim(21)) return 45;
        if (!Status(2, &s) || !s.claimed) return 46;
    }

    /* Event-filter behavior: no definitions in this fixture are filtered. */
    metrics.placement = 2;
    metrics.drift_meters = 100;
    if (!CampaignChallengesOnRace(99, &metrics)) return 38;

    DeleteFileW(L"prebuilt\\campaign-core\\CampaignChallenges.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\UserData\\CampaignEdition\\ChallengeState.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\UserData\\CampaignEdition\\ChallengeState.tmp");
    DeleteFileW(L"prebuilt\\campaign-core\\UserData\\CampaignEdition\\ChallengeClaimPending.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\UserData\\CampaignEdition\\ChallengeClaimPending.tmp");
    return 0;
}
