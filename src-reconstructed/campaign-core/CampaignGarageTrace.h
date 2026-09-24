#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

void __cdecl CampaignGarageTraceWrite(
    uint32_t step,
    void* gs_garage,
    void* holder,
    void* selected,
    int32_t car_id,
    int32_t acquire_ok,
    int32_t owned,
    int32_t callback_status,
    uint32_t revision
);

#ifdef __cplusplus
}
#endif
