#include <windows.h>
#include <stdint.h>
#include "CampaignStartupService.h"
#include "CampaignServices.h"
#include "CampaignEventBus.h"
#include "CampaignGarageUiTrace.h"

static volatile LONG g_startup_lock;
static uint32_t g_startup_state;

static void LockStartup(void) {
    while (InterlockedCompareExchange(&g_startup_lock, 1, 0) != 0) Sleep(0);
}

static void UnlockStartup(void) {
    InterlockedExchange(&g_startup_lock, 0);
}

static void Publish(uint32_t type) {
    CampaignEvent ev;
    ev.size = (uint32_t)sizeof(ev);
    ev.type = type;
    ev.sequence = 0;
    ev.a = 0;
    ev.b = 0;
    ev.c = 0;
    ev.d = 0;
    CampaignEventPublish(&ev);
}

int __cdecl CampaignStartupBegin(void) {
    uint32_t state;

    LockStartup();
    state = g_startup_state;
    UnlockStartup();

    if (state == CAMPAIGN_STARTUP_PROFILE_READY ||
        state == CAMPAIGN_STARTUP_LOBBY_READY) {
        return 1;
    }

    if (state == CAMPAIGN_STARTUP_FAILED) return 0;

    if (!CampaignServiceBoot()) {
        LockStartup();
        g_startup_state = CAMPAIGN_STARTUP_FAILED;
        UnlockStartup();
        return 0;
    }

    /*
      Runtime probe: proves GarageUiTrace path/writer before the garage exists.
      If step 1 exists but step 10 does not, the patched MONTAR callback was
      not the callback actually used by the tutorial screen.
    */
    CampaignGarageUiTraceWrite(1, 0, 0);

    LockStartup();
    g_startup_state = CAMPAIGN_STARTUP_PROFILE_READY;
    UnlockStartup();

    /* CampaignServiceBoot already publishes PROFILE_READY. */
    return 1;
}

int __cdecl CampaignStartupEnterLobby(void) {
    uint32_t state;

    if (!CampaignStartupBegin()) return 0;

    LockStartup();
    state = g_startup_state;
    if (state == CAMPAIGN_STARTUP_PROFILE_READY) {
        g_startup_state = CAMPAIGN_STARTUP_LOBBY_READY;
    }
    UnlockStartup();

    if (state == CAMPAIGN_STARTUP_PROFILE_READY) {
        Publish(CAMPAIGN_EVENT_LOBBY_READY);
    }

    return 1;
}

uint32_t __cdecl CampaignStartupGetState(void) {
    uint32_t state;
    LockStartup();
    state = g_startup_state;
    UnlockStartup();
    return state;
}

void __cdecl CampaignStartupReset(void) {
    LockStartup();
    g_startup_state = CAMPAIGN_STARTUP_COLD;
    UnlockStartup();
}
