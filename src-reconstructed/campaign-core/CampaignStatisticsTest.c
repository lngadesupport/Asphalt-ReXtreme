#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignStatistics.h"

int main(void) {
    CampaignRaceMetrics m;
    CampaignStatisticsSnapshot s;

    DeleteFileW(L"prebuilt\\campaign-core\\UserData\\CampaignEdition\\CampaignStatistics.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\UserData\\CampaignEdition\\CampaignStatistics.tmp");

    ZeroMemory(&m, sizeof(m));
    m.size = sizeof(m);
    m.version = CAMPAIGN_RACE_METRICS_VERSION;
    m.placement = 2;
    m.finish_time_ms = 65000;
    m.drift_meters = 100;
    m.air_time_ms = 1000;
    m.nitro_time_ms = 500;
    m.wrecked_cars = 1;
    m.wrecked_environment = 2;
    m.wrecks_made = 3;
    m.flat_spins = 1;
    m.barrel_rolls = 2;
    m.obstacles_broken = 4;
    m.nitro_all_in = 1;
    m.nitro_chain = 2;
    m.nitro_normal = 3;

    if (!CampaignStatisticsRecordRace(&m)) return 10;

    m.placement = 1;
    m.finish_time_ms = 60000;
    m.drift_meters = 200;
    m.air_time_ms = 2000;
    m.nitro_time_ms = 700;
    m.wrecked_cars = 2;
    m.wrecked_environment = 3;
    m.wrecks_made = 4;
    m.flat_spins = 2;
    m.barrel_rolls = 1;
    m.obstacles_broken = 5;
    m.nitro_all_in = 2;
    m.nitro_chain = 3;
    m.nitro_normal = 4;

    if (!CampaignStatisticsRecordRace(&m)) return 11;

    ZeroMemory(&s, sizeof(s));
    s.size = sizeof(s);
    if (!CampaignStatisticsGet(&s)) return 12;

    if (s.races_with_metrics != 2 || s.wins != 1 || s.podiums != 2) return 13;
    if (s.best_placement != 1 || s.best_finish_time_ms != 60000) return 14;
    if (s.total_drift_meters != 300 ||
        s.total_air_time_ms != 3000 ||
        s.total_nitro_time_ms != 1200) return 15;
    if (s.total_wrecked_cars != 3 ||
        s.total_wrecked_environment != 5 ||
        s.total_wrecks_made != 7) return 16;
    if (s.total_flat_spins != 3 ||
        s.total_barrel_rolls != 3 ||
        s.total_obstacles_broken != 9) return 17;
    if (s.total_nitro_all_in != 3 ||
        s.total_nitro_chain != 5 ||
        s.total_nitro_normal != 7) return 18;

    if (!CampaignStatisticsReset()) return 19;
    ZeroMemory(&s, sizeof(s));
    s.size = sizeof(s);
    if (!CampaignStatisticsGet(&s) || s.races_with_metrics != 0) return 20;

    DeleteFileW(L"prebuilt\\campaign-core\\UserData\\CampaignEdition\\CampaignStatistics.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\UserData\\CampaignEdition\\CampaignStatistics.tmp");
    return 0;
}
