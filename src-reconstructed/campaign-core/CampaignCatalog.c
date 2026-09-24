#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignCatalog.h"

typedef struct CampaignCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignVehicleRecipe vehicles[CAMPAIGN_CATALOG_MAX_VEHICLES];
    uint32_t checksum;
} CampaignCatalogFile;

static CampaignCatalogFile g_catalog;
static volatile LONG g_catalog_loaded;
static WCHAR g_catalog_path[1024];

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

static uint32_t CatalogChecksum(const CampaignCatalogFile* f) {
    return Fnv1a((const unsigned char*)f, (uint32_t)(sizeof(*f) - sizeof(uint32_t)));
}

static int BuildCatalogPath(void) {
    HMODULE module;
    DWORD n;
    uint32_t i;

    ZeroBytes(g_catalog_path, (uint32_t)sizeof(g_catalog_path));

    module = GetModuleHandleW(L"IGPLib_x86.dll");
    if (!module) module = GetModuleHandleW(0);
    if (!module) return 0;

    n = GetModuleFileNameW(module, g_catalog_path, 1024);
    if (n == 0 || n >= 1024) return 0;

    i = n;
    while (i > 0) {
        --i;
        if (g_catalog_path[i] == L'\\' || g_catalog_path[i] == L'/') {
            ++i;
            break;
        }
    }

    {
        static const WCHAR name[] = L"CampaignCatalog.dat";
        uint32_t j = 0;
        while (name[j]) {
            if (i + j + 1 >= 1024) return 0;
            g_catalog_path[i + j] = name[j];
            ++j;
        }
        g_catalog_path[i + j] = 0;
    }

    return 1;
}

static int ValidateCatalog(const CampaignCatalogFile* f) {
    uint32_t i;

    if (!f) return 0;
    if (f->magic != CAMPAIGN_CATALOG_MAGIC) return 0;
    if (f->version != CAMPAIGN_CATALOG_VERSION) return 0;
    if (f->count > CAMPAIGN_CATALOG_MAX_VEHICLES) return 0;
    if (f->checksum != CatalogChecksum(f)) return 0;

    for (i = 0; i < f->count; ++i) {
        const CampaignVehicleRecipe* r = &f->vehicles[i];
        if (r->car_id <= 0) return 0;
        if (r->acquisition_type < CAMPAIGN_ACQUIRE_BLUEPRINT ||
            r->acquisition_type > CAMPAIGN_ACQUIRE_FREE) return 0;
        if (r->cost < 0) return 0;

        if (r->acquisition_type == CAMPAIGN_ACQUIRE_BLUEPRINT && r->item_id <= 0) return 0;
        if (r->acquisition_type != CAMPAIGN_ACQUIRE_BLUEPRINT && r->item_id != 0) return 0;

        if (i > 0 && f->vehicles[i-1].car_id >= r->car_id) return 0;
    }

    return 1;
}

int CampaignCatalogEnsureLoaded(void) {
    HANDLE h;
    DWORD got = 0;

    if (g_catalog_loaded) {
        return g_catalog.count > 0 ? 1 : 0;
    }

    ZeroBytes(&g_catalog, (uint32_t)sizeof(g_catalog));

    if (!BuildCatalogPath()) {
        InterlockedExchange(&g_catalog_loaded, 1);
        return 0;
    }

    h = CreateFileW(
        g_catalog_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );

    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_catalog_loaded, 1);
        return 0;
    }

    if (!ReadFile(h, &g_catalog, (DWORD)sizeof(g_catalog), &got, 0) ||
        got != (DWORD)sizeof(g_catalog)) {
        CloseHandle(h);
        ZeroBytes(&g_catalog, (uint32_t)sizeof(g_catalog));
        InterlockedExchange(&g_catalog_loaded, 1);
        return 0;
    }
    CloseHandle(h);

    if (!ValidateCatalog(&g_catalog)) {
        ZeroBytes(&g_catalog, (uint32_t)sizeof(g_catalog));
        InterlockedExchange(&g_catalog_loaded, 1);
        return 0;
    }

    InterlockedExchange(&g_catalog_loaded, 1);
    return 1;
}

const CampaignVehicleRecipe* CampaignCatalogFind(int32_t car_id) {
    int lo, hi;

    if (car_id <= 0) return 0;
    CampaignCatalogEnsureLoaded();

    lo = 0;
    hi = (int)g_catalog.count - 1;

    while (lo <= hi) {
        int mid = lo + ((hi - lo) / 2);
        int32_t id = g_catalog.vehicles[mid].car_id;

        if (id == car_id) return &g_catalog.vehicles[mid];
        if (id < car_id) lo = mid + 1;
        else hi = mid - 1;
    }

    return 0;
}

const CampaignVehicleRecipe* CampaignCatalogGet(uint32_t index) {
    CampaignCatalogEnsureLoaded();
    if (index >= g_catalog.count) return 0;
    return &g_catalog.vehicles[index];
}

uint32_t CampaignCatalogCount(void) {
    CampaignCatalogEnsureLoaded();
    return g_catalog.count;
}
