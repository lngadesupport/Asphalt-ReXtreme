#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignAchievementCatalog.h"
#include "CampaignStatistics.h"

typedef struct TestAchievementCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignAchievementDefinition entries[CAMPAIGN_ACHIEVEMENT_MAX];
    uint32_t checksum;
} TestAchievementCatalogFile;

static uint32_t Hash(const void* p, uint32_t n) {
    const unsigned char* s = (const unsigned char*)p;
    uint32_t h = 2166136261u, i;
    for (i = 0; i < n; ++i) {
        h ^= s[i];
        h *= 16777619u;
    }
    return h;
}

static int Append(WCHAR* d, uint32_t cap, const WCHAR* s) {
    uint32_t n = 0, i = 0;
    while (d[n]) { ++n; if (n >= cap) return 0; }
    while (s[i]) {
        if (n + 1 >= cap) return 0;
        d[n++] = s[i++];
    }
    d[n] = 0;
    return 1;
}

static int BaseDir(WCHAR* out, uint32_t cap) {
    DWORD n;
    int i;
    n = GetModuleFileNameW(0, out, cap);
    if (n == 0 || n >= cap) return 0;
    i = (int)n - 1;
    while (i >= 0 && out[i] != L'\\' && out[i] != L'/') --i;
    if (i < 0) return 0;
    out[i + 1] = 0;
    return 1;
}

static int BuildPath(WCHAR* out, uint32_t cap, const WCHAR* suffix) {
    uint32_t i;
    for (i = 0; i < cap; ++i) out[i] = 0;
    if (!BaseDir(out, cap)) return 0;
    return Append(out, cap, suffix);
}

static int WriteCatalog(void) {
    TestAchievementCatalogFile file;
    WCHAR path[1024];
    HANDLE h;
    DWORD written = 0;
    uint32_t i;
    unsigned char* q = (unsigned char*)&file;

    for (i = 0; i < (uint32_t)sizeof(file); ++i) q[i] = 0;
    if (!BuildPath(path, 1024, L"CampaignAchievements.dat")) return 0;

    file.magic = CAMPAIGN_ACHIEVEMENT_MAGIC;
    file.version = CAMPAIGN_ACHIEVEMENT_VERSION;
    file.count = 2;

    file.entries[0].achievement_id = 1001;
    file.entries[0].metric = CAMPAIGN_ACHIEVEMENT_WINS;
    file.entries[0].compare = CAMPAIGN_COMPARE_GE;
    file.entries[0].threshold = 1;

    file.entries[1].achievement_id = 1002;
    file.entries[1].metric = CAMPAIGN_ACHIEVEMENT_BEST_FINISH_TIME_MS;
    file.entries[1].compare = CAMPAIGN_COMPARE_LE;
    file.entries[1].threshold = 60000;

    file.checksum = Hash(&file, (uint32_t)sizeof(file) - (uint32_t)sizeof(uint32_t));

    h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;
    if (!WriteFile(h, &file, (DWORD)sizeof(file), &written, 0) || written != (DWORD)sizeof(file)) {
        CloseHandle(h);
        DeleteFileW(path);
        return 0;
    }
    FlushFileBuffers(h);
    CloseHandle(h);
    return 1;
}

static void Cleanup(void) {
    WCHAR path[1024];
    if (BuildPath(path, 1024, L"CampaignAchievements.dat")) DeleteFileW(path);
    if (BuildPath(path, 1024, L"UserData\\CampaignEdition\\AchievementState.dat")) DeleteFileW(path);
    if (BuildPath(path, 1024, L"UserData\\CampaignEdition\\AchievementState.tmp")) DeleteFileW(path);
    if (BuildPath(path, 1024, L"UserData\\CampaignEdition\\CampaignStatistics.dat")) DeleteFileW(path);
    if (BuildPath(path, 1024, L"UserData\\CampaignEdition\\CampaignStatistics.tmp")) DeleteFileW(path);
}

int main(void) {
    CampaignAchievementStatus status;
    CampaignRaceMetrics metrics;

    Cleanup();
    if (!WriteCatalog()) return 1;
    if (!CampaignStatisticsReset()) return 2;
    if (!CampaignAchievementsResetState()) return 3;

    if (CampaignAchievementCatalogCount() != 2) return 4;
    if (!CampaignAchievementsEnsureLoaded()) return 5;

    ZeroMemory(&status, sizeof(status));
    status.size = sizeof(status);
    if (!CampaignAchievementsGetStatus(1001, &status)) return 6;
    if (status.completed || status.current_value != 0 || status.threshold != 1) return 7;

    ZeroMemory(&metrics, sizeof(metrics));
    metrics.size = sizeof(metrics);
    metrics.version = CAMPAIGN_RACE_METRICS_VERSION;
    metrics.placement = 1;
    metrics.finish_time_ms = 50000;
    metrics.drift_meters = 250;
    metrics.air_time_ms = 1200;
    metrics.nitro_time_ms = 5000;

    if (!CampaignStatisticsRecordRace(&metrics)) return 8;
    if (!CampaignAchievementsRefresh()) return 9;

    ZeroMemory(&status, sizeof(status));
    status.size = sizeof(status);
    if (!CampaignAchievementsGetStatus(1001, &status)) return 10;
    if (!status.completed || status.current_value != 1 || status.unlocked_day_key == 0) return 11;

    ZeroMemory(&status, sizeof(status));
    status.size = sizeof(status);
    if (!CampaignAchievementsGetStatus(1002, &status)) return 12;
    if (!status.completed || status.current_value != 50000 || status.unlocked_day_key == 0) return 13;

    if (!CampaignAchievementsResetState()) return 14;
    ZeroMemory(&status, sizeof(status));
    status.size = sizeof(status);
    if (!CampaignAchievementsGetStatusByIndex(0, &status)) return 15;
    if (!status.completed || status.achievement_id != 1001) return 16;

    Cleanup();
    return 0;
}
