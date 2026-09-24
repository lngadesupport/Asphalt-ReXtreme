#pragma once
#include <stdint.h>
#include "CampaignObjectiveCatalog.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_STATISTICS_VERSION 1u

typedef struct CampaignStatisticsSnapshot {
    uint32_t size;
    uint32_t version;
    uint32_t revision;
    uint32_t races_with_metrics;
    uint32_t wins;
    uint32_t podiums;
    uint32_t best_placement;
    uint32_t best_finish_time_ms;
    uint32_t total_drift_meters;
    uint32_t total_air_time_ms;
    uint32_t total_nitro_time_ms;
    uint32_t total_wrecked_cars;
    uint32_t total_wrecked_environment;
    uint32_t total_wrecks_made;
    uint32_t total_flat_spins;
    uint32_t total_barrel_rolls;
    uint32_t total_obstacles_broken;
    uint32_t total_nitro_all_in;
    uint32_t total_nitro_chain;
    uint32_t total_nitro_normal;
} CampaignStatisticsSnapshot;

int CampaignStatisticsEnsureLoaded(void);
int CampaignStatisticsRecordRace(const CampaignRaceMetrics* metrics);
int CampaignStatisticsGet(CampaignStatisticsSnapshot* out);
int CampaignStatisticsReset(void);

#ifdef __cplusplus
}
#endif
