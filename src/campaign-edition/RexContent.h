#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REX_CONTENT_MAX_CARS 256u

typedef struct RexContentDefaults {
    int32_t starter_car_id;
    int32_t starting_credits;
    int32_t starting_tokens;
} RexContentDefaults;

enum RexAcquireMode {
    REX_ACQUIRE_FREE = 1,
    REX_ACQUIRE_CREDITS = 2,
    REX_ACQUIRE_TOKENS = 3
};

typedef struct RexCarDefinition {
    int32_t car_id;
    int32_t acquire_mode;
    int32_t price;
    int32_t class_id;
} RexCarDefinition;

int __cdecl RexContentLoad(void);
uint32_t __cdecl RexContentCarCount(void);
const RexCarDefinition* __cdecl RexContentFirstCar(void);
const RexCarDefinition* __cdecl RexContentFindCar(int32_t car_id);
int __cdecl RexContentDefaultsRead(RexContentDefaults* out);

#ifdef __cplusplus
}
#endif
