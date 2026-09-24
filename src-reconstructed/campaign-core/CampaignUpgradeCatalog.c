#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignUpgradeCatalog.h"

typedef struct CampaignUpgradeCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignUpgradeDefinition entries[CAMPAIGN_UPGRADE_CATALOG_MAX_ENTRIES];
    uint32_t checksum;
} CampaignUpgradeCatalogFile;

static CampaignUpgradeCatalogFile g_upgrade_catalog;
static volatile LONG g_upgrade_catalog_loaded;
static WCHAR g_upgrade_catalog_path[1024];

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

static uint32_t CatalogChecksum(const CampaignUpgradeCatalogFile* f) {
    return Fnv1a((const unsigned char*)f, (uint32_t)(sizeof(*f) - sizeof(uint32_t)));
}

static int BuildCatalogPath(void) {
    HMODULE module;
    DWORD n;
    uint32_t i;
    static const WCHAR name[] = L"CampaignUpgrades.dat";
    uint32_t j = 0;

    ZeroBytes(g_upgrade_catalog_path, (uint32_t)sizeof(g_upgrade_catalog_path));

    module = GetModuleHandleW(L"IGPLib_x86.dll");
    if (!module) module = GetModuleHandleW(0);
    if (!module) return 0;

    n = GetModuleFileNameW(module, g_upgrade_catalog_path, 1024);
    if (n == 0 || n >= 1024) return 0;

    i = n;
    while (i > 0) {
        --i;
        if (g_upgrade_catalog_path[i] == L'\\' || g_upgrade_catalog_path[i] == L'/') {
            ++i;
            break;
        }
    }

    while (name[j]) {
        if (i + j + 1 >= 1024) return 0;
        g_upgrade_catalog_path[i + j] = name[j];
        ++j;
    }
    g_upgrade_catalog_path[i + j] = 0;
    return 1;
}

static int CompareKey(
    const CampaignUpgradeDefinition* a,
    int32_t car_id,
    int32_t kind,
    int32_t part_slot,
    int32_t target_level
) {
    if (a->car_id != car_id) return a->car_id < car_id ? -1 : 1;
    if (a->kind != kind) return a->kind < kind ? -1 : 1;
    if (a->part_slot != part_slot) return a->part_slot < part_slot ? -1 : 1;
    if (a->target_level != target_level) return a->target_level < target_level ? -1 : 1;
    return 0;
}

static int ValidateCatalog(const CampaignUpgradeCatalogFile* f) {
    uint32_t i;

    if (!f) return 0;
    if (f->magic != CAMPAIGN_UPGRADE_CATALOG_MAGIC) return 0;
    if (f->version != CAMPAIGN_UPGRADE_CATALOG_VERSION) return 0;
    if (f->count > CAMPAIGN_UPGRADE_CATALOG_MAX_ENTRIES) return 0;
    if (f->checksum != CatalogChecksum(f)) return 0;

    for (i = 0; i < f->count; ++i) {
        const CampaignUpgradeDefinition* e = &f->entries[i];

        if (e->car_id <= 0) return 0;
        if (e->kind < CAMPAIGN_UPGRADE_KIND_STANDARD || e->kind > CAMPAIGN_UPGRADE_KIND_PROKIT) return 0;
        if (e->part_slot < 0 || e->target_level <= 0) return 0;
        if (e->cost_type < CAMPAIGN_COST_CREDITS || e->cost_type > CAMPAIGN_COST_FREE) return 0;
        if (e->cost < 0 || e->unlock_node_id < 0) return 0;
        if (e->cost_type == CAMPAIGN_COST_INVENTORY && e->item_id <= 0) return 0;
        if (e->cost_type != CAMPAIGN_COST_INVENTORY && e->item_id != 0) return 0;

        if (i > 0) {
            const CampaignUpgradeDefinition* p = &f->entries[i - 1];
            if (CompareKey(e, p->car_id, p->kind, p->part_slot, p->target_level) <= 0) return 0;
        }
    }
    return 1;
}

int CampaignUpgradeCatalogEnsureLoaded(void) {
    HANDLE h;
    DWORD got = 0;

    if (g_upgrade_catalog_loaded) {
        return g_upgrade_catalog.count > 0 ? 1 : 0;
    }

    ZeroBytes(&g_upgrade_catalog, (uint32_t)sizeof(g_upgrade_catalog));

    if (!BuildCatalogPath()) {
        InterlockedExchange(&g_upgrade_catalog_loaded, 1);
        return 0;
    }

    h = CreateFileW(
        g_upgrade_catalog_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );
    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_upgrade_catalog_loaded, 1);
        return 0;
    }

    if (!ReadFile(h, &g_upgrade_catalog, (DWORD)sizeof(g_upgrade_catalog), &got, 0) ||
        got != (DWORD)sizeof(g_upgrade_catalog)) {
        CloseHandle(h);
        ZeroBytes(&g_upgrade_catalog, (uint32_t)sizeof(g_upgrade_catalog));
        InterlockedExchange(&g_upgrade_catalog_loaded, 1);
        return 0;
    }
    CloseHandle(h);

    if (!ValidateCatalog(&g_upgrade_catalog)) {
        ZeroBytes(&g_upgrade_catalog, (uint32_t)sizeof(g_upgrade_catalog));
        InterlockedExchange(&g_upgrade_catalog_loaded, 1);
        return 0;
    }

    InterlockedExchange(&g_upgrade_catalog_loaded, 1);
    return 1;
}

const CampaignUpgradeDefinition* CampaignUpgradeCatalogFind(
    int32_t car_id,
    int32_t kind,
    int32_t part_slot,
    int32_t target_level
) {
    int lo, hi;

    if (car_id <= 0 || part_slot < 0 || target_level <= 0) return 0;
    CampaignUpgradeCatalogEnsureLoaded();

    lo = 0;
    hi = (int)g_upgrade_catalog.count - 1;

    while (lo <= hi) {
        int mid = lo + ((hi - lo) / 2);
        const CampaignUpgradeDefinition* e = &g_upgrade_catalog.entries[mid];
        int cmp = CompareKey(e, car_id, kind, part_slot, target_level);

        if (cmp == 0) return e;
        if (cmp < 0) lo = mid + 1;
        else hi = mid - 1;
    }

    return 0;
}

uint32_t CampaignUpgradeCatalogCount(void) {
    CampaignUpgradeCatalogEnsureLoaded();
    return g_upgrade_catalog.count;
}
