#pragma once
#include <stdint.h>
#include "CampaignObjectiveCatalog.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_CHALLENGE_CATALOG_MAGIC 0x47435852u /* RXCG */
#define CAMPAIGN_CHALLENGE_CATALOG_VERSION 1u
#define CAMPAIGN_CHALLENGE_MAX 128u

enum CampaignChallengeScope {
    CAMPAIGN_CHALLENGE_PERMANENT = 1,
    CAMPAIGN_CHALLENGE_DAILY = 2,
    CAMPAIGN_CHALLENGE_WEEKLY = 3
};

enum CampaignChallengeProgressMode {
    CAMPAIGN_CHALLENGE_SUM_METRIC = 1,
    CAMPAIGN_CHALLENGE_COUNT_MATCHES = 2,
    CAMPAIGN_CHALLENGE_BEST_MAX = 3,
    CAMPAIGN_CHALLENGE_BEST_MIN = 4
};

typedef struct CampaignChallengeDefinition {
    int32_t challenge_id;
    int32_t scope;
    int32_t metric;
    int32_t progress_mode;
    int32_t goal;
    int32_t event_filter_id;
    int32_t qualifier_compare;
    int32_t qualifier_threshold;
    int32_t reward_credits;
    int32_t reward_premium;
    int32_t reward_item_id;
    int32_t reward_item_amount;
    int32_t flags;
    int32_t reserved;
} CampaignChallengeDefinition;

typedef struct CampaignChallengeStatus {
    uint32_t size;
    int32_t challenge_id;
    int32_t scope;
    int32_t metric;
    int32_t progress_mode;
    int32_t goal;
    int32_t progress;
    uint32_t has_progress;
    uint32_t completed;
    uint32_t claimed;
    uint32_t period_key;
    int32_t reward_credits;
    int32_t reward_premium;
    int32_t reward_item_id;
    int32_t reward_item_amount;
} CampaignChallengeStatus;

int CampaignChallengeCatalogEnsureLoaded(void);
uint32_t CampaignChallengeCatalogCount(void);
const CampaignChallengeDefinition* CampaignChallengeCatalogGet(uint32_t index);
const CampaignChallengeDefinition* CampaignChallengeCatalogFind(int32_t challenge_id);

int CampaignChallengesEnsureLoaded(void);
int CampaignChallengesRefreshPeriods(void);
int CampaignChallengesOnRace(int32_t event_id, const CampaignRaceMetrics* metrics);
int CampaignChallengesGetStatus(int32_t challenge_id, CampaignChallengeStatus* out);
int CampaignChallengesGetStatusByIndex(uint32_t index, CampaignChallengeStatus* out);
int CampaignChallengesCanClaim(int32_t challenge_id, CampaignChallengeStatus* out);
int CampaignChallengesMarkClaimed(int32_t challenge_id);
int CampaignChallengesResetState(void);

#ifdef __cplusplus
}
#endif
