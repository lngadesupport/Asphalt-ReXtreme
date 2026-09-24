#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_ORIGINAL_UI_BINDING_MAX 128u
#define CAMPAIGN_ORIGINAL_UI_ID_MAX 32u

enum CampaignOriginalUiKind {
    CAMPAIGN_ORIGINAL_UI_SCREEN = 1,
    CAMPAIGN_ORIGINAL_UI_PANEL = 2,
    CAMPAIGN_ORIGINAL_UI_BUTTON = 3,
    CAMPAIGN_ORIGINAL_UI_SLIDER = 4,
    CAMPAIGN_ORIGINAL_UI_TOGGLE = 5,
    CAMPAIGN_ORIGINAL_UI_LABEL = 6,
    CAMPAIGN_ORIGINAL_UI_POPUP = 7,
    CAMPAIGN_ORIGINAL_UI_LIST = 8,
    CAMPAIGN_ORIGINAL_UI_TAB = 9,
    CAMPAIGN_ORIGINAL_UI_SOUND = 10,
    CAMPAIGN_ORIGINAL_UI_ANIMATION = 11
};

enum CampaignOriginalUiBaseKind {
    CAMPAIGN_ORIGINAL_UI_MODULE_RVA = 1,
    CAMPAIGN_ORIGINAL_UI_POINTER_RVA = 2
};

typedef struct CampaignOriginalUiBinding {
    char id[CAMPAIGN_ORIGINAL_UI_ID_MAX];
    uint32_t kind;
    uint32_t base_kind;
    int32_t field_offset;
    uint32_t target_rva;
    uint32_t semantic;
} CampaignOriginalUiBinding;

enum CampaignOriginalUiFeature {
    CAMPAIGN_ORIGINAL_UI_FEATURE_GRAPHICS_SETTINGS = 1,
    CAMPAIGN_ORIGINAL_UI_FEATURE_CAMERA_SETTINGS = 2,
    CAMPAIGN_ORIGINAL_UI_FEATURE_REPLAY = 3,
    CAMPAIGN_ORIGINAL_UI_FEATURE_PHOTO_MODE = 4,
    CAMPAIGN_ORIGINAL_UI_FEATURE_RACE_HUD = 5,
    CAMPAIGN_ORIGINAL_UI_FEATURE_CHALLENGES = 6,
    CAMPAIGN_ORIGINAL_UI_FEATURE_ACHIEVEMENTS = 7,
    CAMPAIGN_ORIGINAL_UI_FEATURE_RESULTS = 8
};

int CampaignOriginalUiBindingsLoad(void);
uint32_t CampaignOriginalUiBindingsCount(void);
const CampaignOriginalUiBinding* CampaignOriginalUiBindingsGet(uint32_t index);
const CampaignOriginalUiBinding* CampaignOriginalUiBindingsFind(const char* id);
void* CampaignOriginalUiBindingsResolve(const char* id);
int CampaignOriginalUiFeatureReady(uint32_t feature);

#ifdef __cplusplus
}
#endif
