#include <windows.h>
#include <stdint.h>
#include "CampaignGarageFlow.h"
#include "CampaignEventBus.h"

static volatile LONG g_lock;
static CampaignGarageFlowSnapshot g_flow;

static void LockFlow(void) {
    while (InterlockedCompareExchange(&g_lock, 1, 0) != 0) Sleep(0);
}

static void UnlockFlow(void) {
    InterlockedExchange(&g_lock, 0);
}

static void Publish(uint32_t type, int32_t car_id, int32_t result, uint32_t revision) {
    CampaignEvent ev;
    ev.size = (uint32_t)sizeof(ev);
    ev.type = type;
    ev.sequence = 0;
    ev.a = car_id;
    ev.b = result;
    ev.c = (int32_t)revision;
    ev.d = 0;
    CampaignEventPublish(&ev);
}

void __cdecl CampaignGarageFlowBegin(int32_t car_id) {
    LockFlow();
    g_flow.size = (uint32_t)sizeof(g_flow);
    g_flow.state = CAMPAIGN_GARAGE_BUILDING;
    g_flow.car_id = car_id;
    g_flow.result = 0;
    g_flow.revision = 0;
    UnlockFlow();

    Publish(CAMPAIGN_EVENT_BUILD_STARTED, car_id, 0, 0);
}

void __cdecl CampaignGarageFlowCommit(int32_t car_id, uint32_t revision) {
    LockFlow();
    g_flow.size = (uint32_t)sizeof(g_flow);
    g_flow.state = CAMPAIGN_GARAGE_COMMITTED;
    g_flow.car_id = car_id;
    g_flow.result = 1;
    g_flow.revision = revision;
    UnlockFlow();
}

void __cdecl CampaignGarageFlowFrontendCompleted(int32_t car_id, uint32_t revision) {
    LockFlow();
    g_flow.size = (uint32_t)sizeof(g_flow);
    g_flow.state = CAMPAIGN_GARAGE_FRONTEND_COMPLETED;
    g_flow.car_id = car_id;
    g_flow.result = 1;
    g_flow.revision = revision;
    UnlockFlow();

    Publish(CAMPAIGN_EVENT_BUILD_COMPLETED, car_id, 1, revision);
}

void __cdecl CampaignGarageFlowFail(int32_t car_id) {
    LockFlow();
    g_flow.size = (uint32_t)sizeof(g_flow);
    g_flow.state = CAMPAIGN_GARAGE_FAILED;
    g_flow.car_id = car_id;
    g_flow.result = 0;
    g_flow.revision = 0;
    UnlockFlow();

    Publish(CAMPAIGN_EVENT_BUILD_FAILED, car_id, 0, 0);
}

int __cdecl CampaignGarageFlowGet(CampaignGarageFlowSnapshot* out) {
    if (!out || out->size < (uint32_t)sizeof(*out)) return 0;

    LockFlow();
    *out = g_flow;
    UnlockFlow();
    return 1;
}

void __cdecl CampaignGarageFlowReset(void) {
    LockFlow();
    g_flow.size = (uint32_t)sizeof(g_flow);
    g_flow.state = CAMPAIGN_GARAGE_IDLE;
    g_flow.car_id = 0;
    g_flow.result = 0;
    g_flow.revision = 0;
    UnlockFlow();
}
