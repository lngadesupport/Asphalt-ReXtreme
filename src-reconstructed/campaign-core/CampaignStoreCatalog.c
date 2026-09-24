#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignStoreCatalog.h"

typedef struct CampaignStoreCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignStoreOffer offers[CAMPAIGN_STORE_CATALOG_MAX_OFFERS];
    uint32_t checksum;
} CampaignStoreCatalogFile;

static CampaignStoreCatalogFile g_store_catalog;
static volatile LONG g_store_catalog_loaded;
static WCHAR g_store_catalog_path[1024];

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

static uint32_t CatalogChecksum(const CampaignStoreCatalogFile* f) {
    return Fnv1a((const unsigned char*)f, (uint32_t)(sizeof(*f) - sizeof(uint32_t)));
}

static int BuildCatalogPath(void) {
    HMODULE module;
    DWORD n;
    uint32_t i;
    static const WCHAR name[] = L"CampaignStore.dat";
    uint32_t j = 0;

    ZeroBytes(g_store_catalog_path, (uint32_t)sizeof(g_store_catalog_path));

    module = GetModuleHandleW(L"IGPLib_x86.dll");
    if (!module) return 0;

    n = GetModuleFileNameW(module, g_store_catalog_path, 1024);
    if (n == 0 || n >= 1024) return 0;

    i = n;
    while (i > 0) {
        --i;
        if (g_store_catalog_path[i] == L'\\' || g_store_catalog_path[i] == L'/') {
            ++i;
            break;
        }
    }

    while (name[j]) {
        if (i + j + 1 >= 1024) return 0;
        g_store_catalog_path[i + j] = name[j];
        ++j;
    }
    g_store_catalog_path[i + j] = 0;
    return 1;
}

static int ValidateCatalog(const CampaignStoreCatalogFile* f) {
    uint32_t i;

    if (!f) return 0;
    if (f->magic != CAMPAIGN_STORE_CATALOG_MAGIC) return 0;
    if (f->version != CAMPAIGN_STORE_CATALOG_VERSION) return 0;
    if (f->count > CAMPAIGN_STORE_CATALOG_MAX_OFFERS) return 0;
    if (f->checksum != CatalogChecksum(f)) return 0;

    for (i = 0; i < f->count; ++i) {
        const CampaignStoreOffer* e = &f->offers[i];

        if (e->offer_id <= 0 || e->item_id <= 0 || e->quantity <= 0) return 0;
        if (e->currency_type < CAMPAIGN_STORE_CURRENCY_CREDITS ||
            e->currency_type > CAMPAIGN_STORE_CURRENCY_FREE) return 0;
        if (e->price < 0 || e->unlock_node_id < 0) return 0;
        if (e->currency_type == CAMPAIGN_STORE_CURRENCY_FREE && e->price != 0) return 0;
        if (i > 0 && f->offers[i - 1].offer_id >= e->offer_id) return 0;
    }
    return 1;
}

int CampaignStoreCatalogEnsureLoaded(void) {
    HANDLE h;
    DWORD got = 0;

    if (g_store_catalog_loaded) return g_store_catalog.count > 0 ? 1 : 0;
    ZeroBytes(&g_store_catalog, (uint32_t)sizeof(g_store_catalog));

    if (!BuildCatalogPath()) {
        InterlockedExchange(&g_store_catalog_loaded, 1);
        return 0;
    }

    h = CreateFileW(
        g_store_catalog_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );
    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_store_catalog_loaded, 1);
        return 0;
    }

    if (!ReadFile(h, &g_store_catalog, (DWORD)sizeof(g_store_catalog), &got, 0) ||
        got != (DWORD)sizeof(g_store_catalog)) {
        CloseHandle(h);
        ZeroBytes(&g_store_catalog, (uint32_t)sizeof(g_store_catalog));
        InterlockedExchange(&g_store_catalog_loaded, 1);
        return 0;
    }
    CloseHandle(h);

    if (!ValidateCatalog(&g_store_catalog)) {
        ZeroBytes(&g_store_catalog, (uint32_t)sizeof(g_store_catalog));
        InterlockedExchange(&g_store_catalog_loaded, 1);
        return 0;
    }

    InterlockedExchange(&g_store_catalog_loaded, 1);
    return 1;
}

const CampaignStoreOffer* CampaignStoreCatalogFind(int32_t offer_id) {
    int lo, hi;

    if (offer_id <= 0) return 0;
    CampaignStoreCatalogEnsureLoaded();

    lo = 0;
    hi = (int)g_store_catalog.count - 1;

    while (lo <= hi) {
        int mid = lo + ((hi - lo) / 2);
        int32_t id = g_store_catalog.offers[mid].offer_id;

        if (id == offer_id) return &g_store_catalog.offers[mid];
        if (id < offer_id) lo = mid + 1;
        else hi = mid - 1;
    }

    return 0;
}

uint32_t CampaignStoreCatalogCount(void) {
    CampaignStoreCatalogEnsureLoaded();
    return g_store_catalog.count;
}
