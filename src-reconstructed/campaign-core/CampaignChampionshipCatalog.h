#pragma once
#include <stdint.h>
#include "CampaignObjectiveCatalog.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_CHAMPIONSHIP_MAGIC 0x48435852u /* RXCH */
#define CAMPAIGN_CHAMPIONSHIP_VERSION 1u
#define CAMPAIGN_CHAMPIONSHIP_MAX 64u
#define CAMPAIGN_CHAMPIONSHIP_ROUND_MAX 16u
#define CAMPAIGN_CHAMPIONSHIP_POSITION_MAX 7u

typedef struct CampaignChampionshipDefinition {
    int32_t championship_id;
    int32_t required_node_id;
    uint32_t round_count;
    uint32_t flags;
    int32_t round_event_ids[CAMPAIGN_CHAMPIONSHIP_ROUND_MAX];
    int32_t points_by_position[CAMPAIGN_CHAMPIONSHIP_POSITION_MAX];
} CampaignChampionshipDefinition;

typedef struct CampaignChampionshipStatus {
    uint32_t size;
    int32_t championship_id;
    uint32_t round_count;
    uint32_t completed_rounds;
    uint32_t completed;
    int32_t total_points;
} CampaignChampionshipStatus;

typedef struct CampaignChampionshipRoundStatus {
    uint32_t size;
    int32_t championship_id;
    uint32_t round_index;
    int32_t event_id;
    int32_t best_placement;
    int32_t points;
    uint32_t completed;
} CampaignChampionshipRoundStatus;

int CampaignChampionshipCatalogEnsureLoaded(void);
uint32_t CampaignChampionshipCatalogCount(void);
const CampaignChampionshipDefinition* CampaignChampionshipCatalogGet(uint32_t index);
const CampaignChampionshipDefinition* CampaignChampionshipCatalogFind(int32_t championship_id);

int CampaignChampionshipsEnsureLoaded(void);
int CampaignChampionshipsRecordRound(
    int32_t championship_id,
    int32_t event_id,
    const CampaignRaceMetrics* metrics
);
int CampaignChampionshipsGetStatus(
    int32_t championship_id,
    CampaignChampionshipStatus* out
);
int CampaignChampionshipsGetRoundStatus(
    int32_t championship_id,
    uint32_t round_index,
    CampaignChampionshipRoundStatus* out
);
int CampaignChampionshipsReload(void);
int CampaignChampionshipsResetState(void);

#ifdef __cplusplus
}
#endif
