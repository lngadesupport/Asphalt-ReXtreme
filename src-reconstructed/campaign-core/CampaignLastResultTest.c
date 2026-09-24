#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignLastResult.h"

static int BuildPath(WCHAR* out, uint32_t cap, const WCHAR* suffix) {
    DWORD n;
    int i;
    uint32_t p = 0, j = 0;
    n = GetModuleFileNameW(0, out, cap);
    if (n == 0 || n >= cap) return 0;
    i = (int)n - 1;
    while (i >= 0 && out[i] != L'\\' && out[i] != L'/') --i;
    if (i < 0) return 0;
    out[i + 1] = 0;
    while (out[p]) { ++p; if (p >= cap) return 0; }
    while (suffix[j]) {
        if (p + 1 >= cap) return 0;
        out[p++] = suffix[j++];
    }
    out[p] = 0;
    return 1;
}

static void Cleanup(void) {
    WCHAR path[1024];
    if (BuildPath(path, 1024, L"UserData\\CampaignEdition\\LastRaceResult.dat")) DeleteFileW(path);
    if (BuildPath(path, 1024, L"UserData\\CampaignEdition\\LastRaceResult.tmp")) DeleteFileW(path);
}

int main(void) {
    CampaignRaceMetrics metrics;
    CampaignLastResultSnapshot result;

    Cleanup();
    CampaignLastResultClear();

    ZeroMemory(&result, sizeof(result));
    result.size = sizeof(result);
    if (CampaignLastResultGet(&result)) return 1;

    ZeroMemory(&metrics, sizeof(metrics));
    metrics.size = sizeof(metrics);
    metrics.version = CAMPAIGN_RACE_METRICS_VERSION;
    metrics.session_id = 0x12345678u;
    metrics.placement = 2;
    metrics.finish_time_ms = 65432;
    metrics.drift_meters = 345;
    metrics.air_time_ms = 2222;
    metrics.nitro_time_ms = 7777;
    metrics.wrecked_cars = 3;
    metrics.wrecked_environment = 4;
    metrics.wrecks_made = 2;
    metrics.flat_spins = 1;
    metrics.barrel_rolls = 2;
    metrics.obstacles_broken = 5;
    metrics.nitro_all_in = 4;
    metrics.nitro_chain = 6;
    metrics.nitro_normal = 8;
    metrics.stars_awarded = 3;
    metrics.achieved_mask = 5;
    metrics.credits_awarded = 1250;
    metrics.premium_awarded = 2;
    metrics.completion_count = 7;

    if (!CampaignLastResultRecord(501, 77, &metrics, 42)) return 2;

    ZeroMemory(&result, sizeof(result));
    result.size = sizeof(result);
    if (!CampaignLastResultGet(&result)) return 3;
    if (result.event_id != 501 ||
        result.car_id != 77 ||
        result.session_id != 0x12345678u ||
        result.campaign_revision != 42 ||
        result.metrics.placement != 2 ||
        result.metrics.finish_time_ms != 65432 ||
        result.metrics.stars_awarded != 3 ||
        result.metrics.credits_awarded != 1250 ||
        result.metrics.premium_awarded != 2 ||
        result.metrics.completion_count != 7) return 4;

    if (!CampaignLastResultReload()) return 5;
    ZeroMemory(&result, sizeof(result));
    result.size = sizeof(result);
    if (!CampaignLastResultGet(&result)) return 6;
    if (result.metrics.drift_meters != 345 ||
        result.metrics.wrecked_cars != 3 ||
        result.metrics.barrel_rolls != 2 ||
        result.metrics.nitro_chain != 6) return 7;

    if (!CampaignLastResultClear()) return 8;
    ZeroMemory(&result, sizeof(result));
    result.size = sizeof(result);
    if (CampaignLastResultGet(&result)) return 9;

    Cleanup();
    return 0;
}
