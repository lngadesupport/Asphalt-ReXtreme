#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
void __cdecl CampaignGarageUiTraceWrite(
    uint32_t step,
    void* gs_garage,
    void* garage_bottom_bar_widget
);
#ifdef __cplusplus
}
#endif
