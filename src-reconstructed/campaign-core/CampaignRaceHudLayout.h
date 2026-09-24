#pragma once
#include <stdint.h>
#include "CampaignRaceHudBindings.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_RACE_HUD_LAYOUT_MAX 7u

int CampaignRaceHudLayoutLoad(void);
int CampaignRaceHudLayoutSave(void);
int CampaignRaceHudLayoutReset(void);
uint32_t CampaignRaceHudLayoutCount(void);
int CampaignRaceHudLayoutGet(uint32_t index, CampaignRaceHudElementState* out);
int CampaignRaceHudLayoutSet(const CampaignRaceHudElementState* state);
int CampaignRaceHudLayoutApply(void);

#ifdef __cplusplus
}
#endif
