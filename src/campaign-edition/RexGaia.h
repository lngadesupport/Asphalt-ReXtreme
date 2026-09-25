#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#define REX_GAIA_PROFILE_ID_MAX 64u
#define REX_GAIA_PROVIDER_MAX 16u

typedef struct RexGaiaSession {
    char provider[REX_GAIA_PROVIDER_MAX];
    char profile_id[REX_GAIA_PROFILE_ID_MAX];
    int authenticated;
    int offline;
} RexGaiaSession;

typedef struct RexGaia {
    RexGaiaSession session;
    int ready;
} RexGaia;

int RexGaia_Init(
    RexGaia* gaia,
    const char* profile_id
);

int RexGaia_IsReady(
    const RexGaia* gaia
);

int RexGaia_IsNetworkRequired(
    const RexGaia* gaia
);

int RexGaia_GetSession(
    const RexGaia* gaia,
    RexGaiaSession* session
);

#ifdef __cplusplus
}
#endif
