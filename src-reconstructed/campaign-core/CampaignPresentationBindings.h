#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_PRESENTATION_BINDING_MAX 64u
#define CAMPAIGN_PRESENTATION_BINDING_ID_MAX 32u

enum CampaignPresentationBindingBaseKind {
    CAMPAIGN_PRESENTATION_BASE_MODULE_RVA = 1,
    CAMPAIGN_PRESENTATION_BASE_POINTER_RVA = 2
};

enum CampaignPresentationBindingValueKind {
    CAMPAIGN_PRESENTATION_VALUE_I32 = 1,
    CAMPAIGN_PRESENTATION_VALUE_U32 = 2,
    CAMPAIGN_PRESENTATION_VALUE_U8_BOOL = 3,
    CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED = 4
};

enum CampaignPresentationBindingFlags {
    CAMPAIGN_PRESENTATION_BINDING_VERIFIED = 1u << 0
};

typedef struct CampaignPresentationBinding {
    char id[CAMPAIGN_PRESENTATION_BINDING_ID_MAX];
    uint32_t base_kind;
    uint32_t target_rva;
    int32_t field_offset;
    uint32_t value_kind;
    int32_t scale_divisor;
    uint32_t flags;
} CampaignPresentationBinding;

int CampaignPresentationBindingsLoad(void);
uint32_t CampaignPresentationBindingsCount(void);
const CampaignPresentationBinding* CampaignPresentationBindingsFind(const char* id);
int CampaignPresentationBindingsRead(const char* id, int32_t* out_value);
int CampaignPresentationBindingsApply(const char* id, int32_t value);

#ifdef __cplusplus
}
#endif
