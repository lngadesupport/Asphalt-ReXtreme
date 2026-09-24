#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum CampaignStartupState {
    CAMPAIGN_STARTUP_COLD = 0,
    CAMPAIGN_STARTUP_PROFILE_READY = 1,
    CAMPAIGN_STARTUP_LOBBY_READY = 2,
    CAMPAIGN_STARTUP_FAILED = 3
};

int __cdecl CampaignStartupBegin(void);
int __cdecl CampaignStartupEnterLobby(void);
uint32_t __cdecl CampaignStartupGetState(void);
void __cdecl CampaignStartupReset(void);

#ifdef __cplusplus
}
#endif
