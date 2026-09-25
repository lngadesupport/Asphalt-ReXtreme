#pragma once
#include <stddef.h>

#define REX_AMS_HOST_ABI_VERSION 1u

enum RexAmsHostLayoutResult {
    REX_AMS_LAYOUT_OK = 0,
    REX_AMS_LAYOUT_INVALID_ARGUMENT = 1,
    REX_AMS_LAYOUT_MISSING_MANIFEST = 2,
    REX_AMS_LAYOUT_MISSING_GAME = 3,
    REX_AMS_LAYOUT_MISSING_CORE = 4,
    REX_AMS_LAYOUT_MISSING_SHIM = 5,
    REX_AMS_LAYOUT_MISSING_PROXY = 6,
    REX_AMS_LAYOUT_MISSING_CONTENT = 7,
    REX_AMS_LAYOUT_MANIFEST_NOT_REBOUND = 8
};

int RexAmsHost_ValidateLayout(
    const wchar_t* directory
);

const wchar_t* RexAmsHost_DefaultAumid(void);
