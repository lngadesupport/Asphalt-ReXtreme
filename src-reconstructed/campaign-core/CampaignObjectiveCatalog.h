#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_OBJECTIVE_CATALOG_MAGIC 0x4F435852u /* RXCO */
#define CAMPAIGN_OBJECTIVE_CATALOG_VERSION 1u
#define CAMPAIGN_OBJECTIVE_CATALOG_MAX_ENTRIES 1536u

enum CampaignObjectiveMetric {
    CAMPAIGN_METRIC_PLACEMENT = 1,
    CAMPAIGN_METRIC_FINISH_TIME_MS = 2,
    CAMPAIGN_METRIC_DRIFT_METERS = 3,
    CAMPAIGN_METRIC_AIR_TIME_MS = 4,
    CAMPAIGN_METRIC_NITRO_TIME_MS = 5,
    CAMPAIGN_METRIC_WRECKED_CARS = 6,
    CAMPAIGN_METRIC_WRECKED_ENVIRONMENT = 7,
    CAMPAIGN_METRIC_WRECKS_MADE = 8,
    CAMPAIGN_METRIC_FLAT_SPINS = 9,
    CAMPAIGN_METRIC_BARREL_ROLLS = 10,
    CAMPAIGN_METRIC_OBSTACLES_BROKEN = 11,
    CAMPAIGN_METRIC_NITRO_ALL_IN = 12,
    CAMPAIGN_METRIC_NITRO_CHAIN = 13,
    CAMPAIGN_METRIC_NITRO_NORMAL = 14
};

enum CampaignObjectiveCompare {
    CAMPAIGN_COMPARE_LE = 1,
    CAMPAIGN_COMPARE_GE = 2,
    CAMPAIGN_COMPARE_EQ = 3
};

typedef struct CampaignObjectiveDefinition {
    int32_t event_id;
    int32_t objective_index;
    int32_t metric;
    int32_t compare;
    int32_t threshold;
    int32_t stars;
    int32_t flags;
    int32_t reserved;
} CampaignObjectiveDefinition;

typedef struct CampaignRaceMetrics {
    uint32_t size;
    uint32_t version;
    uint32_t session_id;

    int32_t placement;
    int32_t finish_time_ms;

    int32_t drift_meters;
    int32_t air_time_ms;
    int32_t nitro_time_ms;

    int32_t wrecked_cars;
    int32_t wrecked_environment;
    int32_t wrecks_made;

    int32_t flat_spins;
    int32_t barrel_rolls;
    int32_t obstacles_broken;

    int32_t nitro_all_in;
    int32_t nitro_chain;
    int32_t nitro_normal;

    int32_t stars_awarded;
    int32_t achieved_mask;
    int32_t credits_awarded;
    int32_t premium_awarded;
    int32_t completion_count;
} CampaignRaceMetrics;

#define CAMPAIGN_RACE_METRICS_VERSION 1u

int CampaignObjectiveCatalogEnsureLoaded(void);
uint32_t CampaignObjectiveCatalogCount(void);
int CampaignObjectiveEvaluate(
    int32_t event_id,
    const CampaignRaceMetrics* metrics,
    int32_t* stars_out,
    int32_t* achieved_mask_out
);

#ifdef __cplusplus
}
#endif
