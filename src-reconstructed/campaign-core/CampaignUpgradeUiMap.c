#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignUpgradeUiMap.h"
#include "CampaignUpgradeCatalog.h"

typedef struct CampaignUpgradeUiMapFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignUpgradeUiEntry entries[CAMPAIGN_UPGRADE_UI_MAP_MAX_ENTRIES];
    uint32_t checksum;
} CampaignUpgradeUiMapFile;

static CampaignUpgradeUiMapFile g_ui_map;
static volatile LONG g_ui_map_loaded;
static WCHAR g_ui_map_path[1024];

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

static uint32_t MapChecksum(const CampaignUpgradeUiMapFile* f) {
    return Fnv1a((const unsigned char*)f, (uint32_t)(sizeof(*f) - sizeof(uint32_t)));
}

static int BuildPath(void) {
    HMODULE module;
    DWORD n;
    uint32_t i, j = 0;
    static const WCHAR name[] = L"CampaignUpgradeUiMap.dat";

    ZeroBytes(g_ui_map_path, (uint32_t)sizeof(g_ui_map_path));
    module = GetModuleHandleW(L"IGPLib_x86.dll");
    if (!module) return 0;

    n = GetModuleFileNameW(module, g_ui_map_path, 1024);
    if (n == 0 || n >= 1024) return 0;

    i = n;
    while (i > 0) {
        --i;
        if (g_ui_map_path[i] == L'\\' || g_ui_map_path[i] == L'/') {
            ++i;
            break;
        }
    }

    while (name[j]) {
        if (i + j + 1 >= 1024) return 0;
        g_ui_map_path[i + j] = name[j];
        ++j;
    }
    g_ui_map_path[i + j] = 0;
    return 1;
}

static int Validate(const CampaignUpgradeUiMapFile* f) {
    uint32_t i;
    if (!f) return 0;
    if (f->magic != CAMPAIGN_UPGRADE_UI_MAP_MAGIC) return 0;
    if (f->version != CAMPAIGN_UPGRADE_UI_MAP_VERSION) return 0;
    if (f->count > CAMPAIGN_UPGRADE_UI_MAP_MAX_ENTRIES) return 0;
    if (f->checksum != MapChecksum(f)) return 0;

    for (i = 0; i < f->count; ++i) {
        const CampaignUpgradeUiEntry* e = &f->entries[i];
        if (e->ui_action_id <= 0) return 0;
        if (e->kind < CAMPAIGN_UPGRADE_KIND_STANDARD ||
            e->kind > CAMPAIGN_UPGRADE_KIND_PROKIT) return 0;
        if (e->part_slot < 0) return 0;
        if (i > 0 && f->entries[i - 1].ui_action_id >= e->ui_action_id) return 0;
    }
    return 1;
}

int CampaignUpgradeUiMapEnsureLoaded(void) {
    HANDLE h;
    DWORD got = 0;

    if (g_ui_map_loaded) return g_ui_map.count > 0 ? 1 : 0;
    ZeroBytes(&g_ui_map, (uint32_t)sizeof(g_ui_map));

    if (!BuildPath()) {
        InterlockedExchange(&g_ui_map_loaded, 1);
        return 0;
    }

    h = CreateFileW(
        g_ui_map_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );
    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_ui_map_loaded, 1);
        return 0;
    }

    if (!ReadFile(h, &g_ui_map, (DWORD)sizeof(g_ui_map), &got, 0) ||
        got != (DWORD)sizeof(g_ui_map)) {
        CloseHandle(h);
        ZeroBytes(&g_ui_map, (uint32_t)sizeof(g_ui_map));
        InterlockedExchange(&g_ui_map_loaded, 1);
        return 0;
    }
    CloseHandle(h);

    if (!Validate(&g_ui_map)) {
        ZeroBytes(&g_ui_map, (uint32_t)sizeof(g_ui_map));
        InterlockedExchange(&g_ui_map_loaded, 1);
        return 0;
    }

    InterlockedExchange(&g_ui_map_loaded, 1);
    return 1;
}

const CampaignUpgradeUiEntry* CampaignUpgradeUiMapFind(int32_t ui_action_id) {
    int lo, hi;

    if (ui_action_id <= 0) return 0;
    CampaignUpgradeUiMapEnsureLoaded();

    lo = 0;
    hi = (int)g_ui_map.count - 1;

    while (lo <= hi) {
        int mid = lo + ((hi - lo) / 2);
        int32_t id = g_ui_map.entries[mid].ui_action_id;
        if (id == ui_action_id) return &g_ui_map.entries[mid];
        if (id < ui_action_id) lo = mid + 1;
        else hi = mid - 1;
    }
    return 0;
}

uint32_t CampaignUpgradeUiMapCount(void) {
    CampaignUpgradeUiMapEnsureLoaded();
    return g_ui_map.count;
}
