#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_PRESENTATION_CAPABILITY_MAX 64u
#define CAMPAIGN_PRESENTATION_CAPABILITY_ID_MAX 32u

enum CampaignPresentationCapabilityKind {
    CAMPAIGN_PRESENTATION_CAPABILITY_TOGGLE = 1,
    CAMPAIGN_PRESENTATION_CAPABILITY_CHOICE = 2,
    CAMPAIGN_PRESENTATION_CAPABILITY_SLIDER = 3
};

enum CampaignPresentationCapabilityFlags {
    CAMPAIGN_PRESENTATION_CAPABILITY_VERIFIED = 1u << 0,
    CAMPAIGN_PRESENTATION_CAPABILITY_RESTART_REQUIRED = 1u << 1
};

typedef struct CampaignPresentationCapability {
    char id[CAMPAIGN_PRESENTATION_CAPABILITY_ID_MAX];
    uint32_t kind;
    int32_t minimum;
    int32_t maximum;
    int32_t step;
    int32_t original_value;
    uint32_t flags;
} CampaignPresentationCapability;

int CampaignPresentationCatalogLoad(void);
uint32_t CampaignPresentationCatalogCount(void);
const CampaignPresentationCapability* CampaignPresentationCatalogGet(uint32_t index);
const CampaignPresentationCapability* CampaignPresentationCatalogFind(const char* id);

#ifdef __cplusplus
}
#endif
