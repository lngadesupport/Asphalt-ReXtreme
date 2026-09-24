#pragma once
#include <stdint.h>
#include "CampaignApplication.h"

#ifdef __cplusplus
extern "C" {
#endif

int __cdecl CampaignFrontendDispatch(
    const CampaignIntent* intent,
    CampaignViewModel* out
);
int __cdecl CampaignFrontendRead(CampaignViewModel* out);
int __cdecl CampaignFrontendBuildSelected(void);
int __cdecl CampaignFrontendSelectCar(int32_t car_id);

#ifdef __cplusplus
}
#endif
