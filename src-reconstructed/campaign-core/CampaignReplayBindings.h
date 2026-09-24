#pragma once
#include <stdint.h>
#include "CampaignPresentation.h"
#include "CampaignPresentationBindings.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_REPLAY_BINDING_MAX 32u
#define CAMPAIGN_REPLAY_BINDING_CHAIN_MAX 4u

enum CampaignReplayBindingSemantic {
    CAMPAIGN_REPLAY_BIND_TIME_MS = 1,
    CAMPAIGN_REPLAY_BIND_ENTITY_ID = 2,
    CAMPAIGN_REPLAY_BIND_POSITION_X = 3,
    CAMPAIGN_REPLAY_BIND_POSITION_Y = 4,
    CAMPAIGN_REPLAY_BIND_POSITION_Z = 5,
    CAMPAIGN_REPLAY_BIND_ROTATION_X = 6,
    CAMPAIGN_REPLAY_BIND_ROTATION_Y = 7,
    CAMPAIGN_REPLAY_BIND_ROTATION_Z = 8,
    CAMPAIGN_REPLAY_BIND_ROTATION_W = 9,
    CAMPAIGN_REPLAY_BIND_VELOCITY_X = 10,
    CAMPAIGN_REPLAY_BIND_VELOCITY_Y = 11,
    CAMPAIGN_REPLAY_BIND_VELOCITY_Z = 12,
    CAMPAIGN_REPLAY_BIND_STATE_FLAGS = 13
};

enum CampaignReplayBindingRootKind {
    CAMPAIGN_REPLAY_ROOT_GUI_ARGUMENT = 1,
    CAMPAIGN_REPLAY_ROOT_MODULE_RVA = 2,
    CAMPAIGN_REPLAY_ROOT_POINTER_RVA = 3
};

enum CampaignReplayBindingFlags {
    CAMPAIGN_REPLAY_BINDING_VERIFIED = 1u << 0,
    CAMPAIGN_REPLAY_BINDING_OPTIONAL = 1u << 1
};

typedef struct CampaignReplayBinding {
    uint32_t semantic;
    uint32_t root_kind;
    uint32_t root_rva;
    uint32_t chain_count;
    int32_t chain_offsets[CAMPAIGN_REPLAY_BINDING_CHAIN_MAX];
    int32_t field_offset;
    uint32_t value_kind;
    int32_t scale_divisor;
    uint32_t flags;
} CampaignReplayBinding;

int CampaignReplayBindingsLoad(void);
uint32_t CampaignReplayBindingsCount(void);
const CampaignReplayBinding* CampaignReplayBindingsFind(uint32_t semantic);
int CampaignReplayBindingsReady(void);
int CampaignReplayBindingsSample(void* game_mode_gui, CampaignReplaySample* out);

#ifdef __cplusplus
}
#endif
