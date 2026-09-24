#pragma once
#include <stdint.h>
#include "CampaignStatistics.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_ACHIEVEMENT_MAGIC 0x47415852u /* RXAG */
#define CAMPAIGN_ACHIEVEMENT_VERSION 1u
#define CAMPAIGN_ACHIEVEMENT_MAX 128u

enum CampaignAchievementMetric {
    CAMPAIGN_ACHIEVEMENT_RACES = 1,
    CAMPAIGN_ACHIEVEMENT_WINS = 2,
    CAMPAIGN_ACHIEVEMENT_PODIUMS = 3,
    CAMPAIGN_ACHIEVEMENT_BEST_PLACEMENT = 4,
    CAMPAIGN_ACHIEVEMENT_BEST_FINISH_TIME_MS = 5,
    CAMPAIGN_ACHIEVEMENT_DRIFT_METERS = 6,
    CAMPAIGN_ACHIEVEMENT_AIR_TIME_MS = 7,
    CAMPAIGN_ACHIEVEMENT_NITRO_TIME_MS = 8,
    CAMPAIGN_ACHIEVEMENT_WRECKED_CARS = 9,
    CAMPAIGN_ACHIEVEMENT_WRECKED_ENVIRONMENT = 10,
    CAMPAIGN_ACHIEVEMENT_WRECKS_MADE = 11,
    CAMPAIGN_ACHIEVEMENT_FLAT_SPINS = 12,
    CAMPAIGN_ACHIEVEMENT_BARREL_ROLLS = 13,
    CAMPAIGN_ACHIEVEMENT_OBSTACLES_BROKEN = 14,
    CAMPAIGN_ACHIEVEMENT_NITRO_ALL_IN = 15,
    CAMPAIGN_ACHIEVEMENT_NITRO_CHAIN = 16,
    CAMPAIGN_ACHIEVEMENT_NITRO_NORMAL = 17
};

typedef struct CampaignAchievementDefinition {
    int32_t achievement_id;
    uint32_t metric;
    uint32_t compare;
    uint32_t threshold;
    uint32_t flags;
    uint32_t reserved0;
    uint32_t reserved1;
    uint32_t reserved2;
} CampaignAchievementDefinition;

typedef struct CampaignAchievementStatus {
    uint32_t size;
    int32_t achievement_id;
    uint32_t metric;
    uint32_t compare;
    uint32_t threshold;
    uint32_t current_value;
    uint32_t completed;
    uint32_t unlocked_day_key;
} CampaignAchievementStatus;

int CampaignAchievementCatalogEnsureLoaded(void);
uint32_t CampaignAchievementCatalogCount(void);
const CampaignAchievementDefinition* CampaignAchievementCatalogGet(uint32_t index);
const CampaignAchievementDefinition* CampaignAchievementCatalogFind(int32_t achievement_id);

int CampaignAchievementsEnsureLoaded(void);
int CampaignAchievementsRefresh(void);
int CampaignAchievementsGetStatus(int32_t achievement_id, CampaignAchievementStatus* out);
int CampaignAchievementsGetStatusByIndex(uint32_t index, CampaignAchievementStatus* out);
int CampaignAchievementsResetState(void);

#ifdef __cplusplus
}
#endif
