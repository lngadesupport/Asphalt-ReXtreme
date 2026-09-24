#pragma once
#include <stdint.h>
#include "CampaignPresentationBindings.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_RACE_HUD_BINDING_MAX 128u

enum CampaignRaceHudElement {
    CAMPAIGN_RACE_HUD_POSITION = 1,
    CAMPAIGN_RACE_HUD_SPEED = 2,
    CAMPAIGN_RACE_HUD_NITRO = 3,
    CAMPAIGN_RACE_HUD_LAP = 4,
    CAMPAIGN_RACE_HUD_TIMER = 5,
    CAMPAIGN_RACE_HUD_MINIMAP = 6,
    CAMPAIGN_RACE_HUD_OBJECTIVE = 7
};

enum CampaignRaceHudProperty {
    CAMPAIGN_RACE_HUD_PROP_X = 1,
    CAMPAIGN_RACE_HUD_PROP_Y = 2,
    CAMPAIGN_RACE_HUD_PROP_SCALE = 3,
    CAMPAIGN_RACE_HUD_PROP_OPACITY = 4,
    CAMPAIGN_RACE_HUD_PROP_VISIBLE = 5
};

enum CampaignRaceHudStateFlags {
    CAMPAIGN_RACE_HUD_SET_X = 1u << 0,
    CAMPAIGN_RACE_HUD_SET_Y = 1u << 1,
    CAMPAIGN_RACE_HUD_SET_SCALE = 1u << 2,
    CAMPAIGN_RACE_HUD_SET_OPACITY = 1u << 3,
    CAMPAIGN_RACE_HUD_SET_VISIBLE = 1u << 4
};

typedef struct CampaignRaceHudBinding {
    uint32_t element;
    uint32_t property;
    uint32_t base_kind;
    uint32_t target_rva;
    int32_t field_offset;
    uint32_t value_kind;
    int32_t scale_divisor;
    uint32_t flags;
} CampaignRaceHudBinding;

typedef struct CampaignRaceHudElementState {
    uint32_t size;
    uint32_t element;
    uint32_t set_flags;
    int32_t x_x1000;
    int32_t y_x1000;
    int32_t scale_x1000;
    int32_t opacity_x1000;
    int32_t visible;
} CampaignRaceHudElementState;

int CampaignRaceHudBindingsLoad(void);
uint32_t CampaignRaceHudBindingsCount(void);
const CampaignRaceHudBinding* CampaignRaceHudBindingsFind(uint32_t element, uint32_t property);
int CampaignRaceHudElementReady(uint32_t element, uint32_t property_mask);
int CampaignRaceHudApplyElement(const CampaignRaceHudElementState* state);

#ifdef __cplusplus
}
#endif
