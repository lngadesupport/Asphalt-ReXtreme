#pragma once
#include <stdint.h>
#include "RexCampaign.h"

#ifdef __cplusplus
extern "C" {
#endif

int __cdecl RexStateBoot(void);
int __cdecl RexStateRead(RexViewState* out);
int __cdecl RexStateSelectCar(int32_t car_id);
int __cdecl RexStateBuildSelected(void);

#ifdef __cplusplus
}
#endif
