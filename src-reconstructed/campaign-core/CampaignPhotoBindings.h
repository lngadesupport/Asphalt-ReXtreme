#pragma once
#include <stdint.h>
#include "CampaignPresentation.h"
#include "CampaignPresentationBindings.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_PHOTO_BINDING_MAX 32u

enum CampaignPhotoBindingSemantic {
    CAMPAIGN_PHOTO_BIND_POSITION_X = 1,
    CAMPAIGN_PHOTO_BIND_POSITION_Y = 2,
    CAMPAIGN_PHOTO_BIND_POSITION_Z = 3,
    CAMPAIGN_PHOTO_BIND_PITCH = 4,
    CAMPAIGN_PHOTO_BIND_YAW = 5,
    CAMPAIGN_PHOTO_BIND_ROLL = 6,
    CAMPAIGN_PHOTO_BIND_FOV = 7,
    CAMPAIGN_PHOTO_BIND_HUD_VISIBLE = 8
};

typedef struct CampaignPhotoBinding {
    uint32_t semantic;
    uint32_t base_kind;
    uint32_t target_rva;
    int32_t field_offset;
    uint32_t value_kind;
    int32_t scale_divisor;
    uint32_t flags;
} CampaignPhotoBinding;

int CampaignPhotoBindingsLoad(void);
uint32_t CampaignPhotoBindingsCount(void);
const CampaignPhotoBinding* CampaignPhotoBindingsFind(uint32_t semantic);
int CampaignPhotoBindingsReady(uint32_t camera_mode);
int CampaignPhotoBindingsApply(const CampaignPhotoState* state);

#ifdef __cplusplus
}
#endif
