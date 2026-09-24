#include <windows.h>
#include <stdint.h>
#include "CampaignEventBus.h"

static CampaignEvent g_events[CAMPAIGN_EVENT_BUS_CAPACITY];
static volatile LONG g_event_lock;
static uint32_t g_head;
static uint32_t g_tail;
static uint32_t g_count;
static uint32_t g_sequence;

static void LockBus(void) {
    while (InterlockedCompareExchange(&g_event_lock, 1, 0) != 0) Sleep(0);
}

static void UnlockBus(void) {
    InterlockedExchange(&g_event_lock, 0);
}

static void CopyEvent(CampaignEvent* dst, const CampaignEvent* src) {
    dst->size = src->size;
    dst->type = src->type;
    dst->sequence = src->sequence;
    dst->a = src->a;
    dst->b = src->b;
    dst->c = src->c;
    dst->d = src->d;
}

int __cdecl CampaignEventPublish(const CampaignEvent* event) {
    CampaignEvent copy;

    if (!event || event->size < (uint32_t)sizeof(CampaignEvent)) return 0;
    if (event->type == CAMPAIGN_EVENT_NONE) return 0;

    copy = *event;

    LockBus();

    ++g_sequence;
    if (!g_sequence) ++g_sequence;
    copy.sequence = g_sequence;

    if (g_count == CAMPAIGN_EVENT_BUS_CAPACITY) {
        g_head = (g_head + 1u) % CAMPAIGN_EVENT_BUS_CAPACITY;
        --g_count;
    }

    CopyEvent(&g_events[g_tail], &copy);
    g_tail = (g_tail + 1u) % CAMPAIGN_EVENT_BUS_CAPACITY;
    ++g_count;

    UnlockBus();
    return 1;
}

int __cdecl CampaignEventPoll(CampaignEvent* event) {
    if (!event || event->size < (uint32_t)sizeof(CampaignEvent)) return 0;

    LockBus();

    if (!g_count) {
        UnlockBus();
        return 0;
    }

    CopyEvent(event, &g_events[g_head]);
    g_head = (g_head + 1u) % CAMPAIGN_EVENT_BUS_CAPACITY;
    --g_count;

    UnlockBus();
    return 1;
}

uint32_t __cdecl CampaignEventPendingCount(void) {
    uint32_t count;
    LockBus();
    count = g_count;
    UnlockBus();
    return count;
}

void __cdecl CampaignEventReset(void) {
    LockBus();
    g_head = 0;
    g_tail = 0;
    g_count = 0;
    UnlockBus();
}
