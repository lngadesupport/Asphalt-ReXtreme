#include "RexGaia.h"

#include <string.h>

int RexGaia_Init(
    RexGaia* gaia,
    const char* profile_id
) {
    if (gaia == 0 ||
        profile_id == 0 ||
        profile_id[0] == '\0') {
        return 0;
    }

    memset(gaia, 0, sizeof(*gaia));

    if (strcpy_s(
            gaia->session.provider,
            sizeof(gaia->session.provider),
            "rex-local") != 0 ||
        strcpy_s(
            gaia->session.profile_id,
            sizeof(gaia->session.profile_id),
            profile_id) != 0) {
        memset(gaia, 0, sizeof(*gaia));
        return 0;
    }

    gaia->session.authenticated = 1;
    gaia->session.offline = 1;
    gaia->ready = 1;
    return 1;
}

int RexGaia_IsReady(
    const RexGaia* gaia
) {
    return gaia != 0 && gaia->ready;
}

int RexGaia_IsNetworkRequired(
    const RexGaia* gaia
) {
    (void)gaia;
    return 0;
}

int RexGaia_GetSession(
    const RexGaia* gaia,
    RexGaiaSession* session
) {
    if (gaia == 0 ||
        session == 0 ||
        !gaia->ready) {
        return 0;
    }

    *session = gaia->session;
    return 1;
}
