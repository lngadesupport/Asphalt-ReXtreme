#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignEventCatalog.h"

typedef struct CampaignEventCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignEventDefinition events[CAMPAIGN_EVENT_CATALOG_MAX_EVENTS];
    uint32_t checksum;
} CampaignEventCatalogFile;

static CampaignEventCatalogFile g_event_catalog;
static volatile LONG g_event_catalog_loaded;
static WCHAR g_event_catalog_path[1024];

static void ZeroBytes(void* p, uint32_t count) {
    volatile unsigned char* q = (volatile unsigned char*)p;
    uint32_t i;
    for (i = 0; i < count; ++i) q[i] = 0;
}

static uint32_t Fnv1a(const unsigned char* data, uint32_t count) {
    uint32_t h = 2166136261u, i;
    for (i = 0; i < count; ++i) {
        h ^= data[i];
        h *= 16777619u;
    }
    return h;
}

static uint32_t CatalogChecksum(const CampaignEventCatalogFile* f) {
    return Fnv1a((const unsigned char*)f, (uint32_t)(sizeof(*f) - sizeof(uint32_t)));
}

static int BuildCatalogPath(void) {
    HMODULE module;
    DWORD n;
    uint32_t i;
    static const WCHAR name[] = L"CampaignEvents.dat";
    uint32_t j = 0;

    ZeroBytes(g_event_catalog_path, (uint32_t)sizeof(g_event_catalog_path));

    module = GetModuleHandleW(L"IGPLib_x86.dll");
    if (!module) return 0;

    n = GetModuleFileNameW(module, g_event_catalog_path, 1024);
    if (n == 0 || n >= 1024) return 0;

    i = n;
    while (i > 0) {
        --i;
        if (g_event_catalog_path[i] == L'\\' || g_event_catalog_path[i] == L'/') {
            ++i;
            break;
        }
    }

    while (name[j]) {
        if (i + j + 1 >= 1024) return 0;
        g_event_catalog_path[i + j] = name[j];
        ++j;
    }
    g_event_catalog_path[i + j] = 0;
    return 1;
}

static int ValidateCatalog(const CampaignEventCatalogFile* f) {
    uint32_t i;

    if (!f) return 0;
    if (f->magic != CAMPAIGN_EVENT_CATALOG_MAGIC) return 0;
    if (f->version != CAMPAIGN_EVENT_CATALOG_VERSION) return 0;
    if (f->count > CAMPAIGN_EVENT_CATALOG_MAX_EVENTS) return 0;
    if (f->checksum != CatalogChecksum(f)) return 0;

    for (i = 0; i < f->count; ++i) {
        const CampaignEventDefinition* e = &f->events[i];

        if (e->event_id <= 0) return 0;
        if (e->required_node_id < 0 || e->completion_node_id < 0) return 0;
        if (e->participation_credits < 0 ||
            e->position1_credits < 0 ||
            e->position2_credits < 0 ||
            e->position3_credits < 0 ||
            e->premium_reward < 0) return 0;
        if (e->max_stars < 0 || e->max_stars > 10) return 0;

        if (i > 0 && f->events[i - 1].event_id >= e->event_id) return 0;
    }

    return 1;
}

int CampaignEventCatalogEnsureLoaded(void) {
    HANDLE h;
    DWORD got = 0;

    if (g_event_catalog_loaded) {
        return g_event_catalog.count > 0 ? 1 : 0;
    }

    ZeroBytes(&g_event_catalog, (uint32_t)sizeof(g_event_catalog));

    if (!BuildCatalogPath()) {
        InterlockedExchange(&g_event_catalog_loaded, 1);
        return 0;
    }

    h = CreateFileW(
        g_event_catalog_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );

    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_event_catalog_loaded, 1);
        return 0;
    }

    if (!ReadFile(h, &g_event_catalog, (DWORD)sizeof(g_event_catalog), &got, 0) ||
        got != (DWORD)sizeof(g_event_catalog)) {
        CloseHandle(h);
        ZeroBytes(&g_event_catalog, (uint32_t)sizeof(g_event_catalog));
        InterlockedExchange(&g_event_catalog_loaded, 1);
        return 0;
    }
    CloseHandle(h);

    if (!ValidateCatalog(&g_event_catalog)) {
        ZeroBytes(&g_event_catalog, (uint32_t)sizeof(g_event_catalog));
        InterlockedExchange(&g_event_catalog_loaded, 1);
        return 0;
    }

    InterlockedExchange(&g_event_catalog_loaded, 1);
    return 1;
}

const CampaignEventDefinition* CampaignEventCatalogFind(int32_t event_id) {
    int lo, hi;

    if (event_id <= 0) return 0;
    CampaignEventCatalogEnsureLoaded();

    lo = 0;
    hi = (int)g_event_catalog.count - 1;

    while (lo <= hi) {
        int mid = lo + ((hi - lo) / 2);
        int32_t id = g_event_catalog.events[mid].event_id;

        if (id == event_id) return &g_event_catalog.events[mid];
        if (id < event_id) lo = mid + 1;
        else hi = mid - 1;
    }

    return 0;
}

uint32_t CampaignEventCatalogCount(void) {
    CampaignEventCatalogEnsureLoaded();
    return g_event_catalog.count;
}
