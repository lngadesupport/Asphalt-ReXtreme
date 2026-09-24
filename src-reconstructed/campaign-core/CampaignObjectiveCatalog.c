#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignObjectiveCatalog.h"

typedef struct CampaignObjectiveCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignObjectiveDefinition entries[CAMPAIGN_OBJECTIVE_CATALOG_MAX_ENTRIES];
    uint32_t checksum;
} CampaignObjectiveCatalogFile;

static CampaignObjectiveCatalogFile g_objectives;
static volatile LONG g_objectives_loaded;
static WCHAR g_objectives_path[1024];

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

static uint32_t CatalogChecksum(const CampaignObjectiveCatalogFile* f) {
    return Fnv1a(
        (const unsigned char*)f,
        (uint32_t)(sizeof(*f) - sizeof(uint32_t))
    );
}

static int BuildCatalogPath(void) {
    HMODULE module;
    DWORD n;
    uint32_t i;
    uint32_t j = 0;
    static const WCHAR name[] = L"CampaignObjectives.dat";

    ZeroBytes(g_objectives_path, (uint32_t)sizeof(g_objectives_path));

    module = GetModuleHandleW(L"IGPLib_x86.dll");
    if (!module) return 0;

    n = GetModuleFileNameW(module, g_objectives_path, 1024);
    if (n == 0 || n >= 1024) return 0;

    i = n;
    while (i > 0) {
        --i;
        if (g_objectives_path[i] == L'\\' || g_objectives_path[i] == L'/') {
            ++i;
            break;
        }
    }

    while (name[j]) {
        if (i + j + 1 >= 1024) return 0;
        g_objectives_path[i + j] = name[j];
        ++j;
    }
    g_objectives_path[i + j] = 0;
    return 1;
}

static int CompareKey(
    const CampaignObjectiveDefinition* e,
    int32_t event_id,
    int32_t objective_index
) {
    if (e->event_id != event_id) return e->event_id < event_id ? -1 : 1;
    if (e->objective_index != objective_index) {
        return e->objective_index < objective_index ? -1 : 1;
    }
    return 0;
}

static int ValidateCatalog(const CampaignObjectiveCatalogFile* f) {
    uint32_t i;

    if (!f) return 0;
    if (f->magic != CAMPAIGN_OBJECTIVE_CATALOG_MAGIC) return 0;
    if (f->version != CAMPAIGN_OBJECTIVE_CATALOG_VERSION) return 0;
    if (f->count > CAMPAIGN_OBJECTIVE_CATALOG_MAX_ENTRIES) return 0;
    if (f->checksum != CatalogChecksum(f)) return 0;

    for (i = 0; i < f->count; ++i) {
        const CampaignObjectiveDefinition* e = &f->entries[i];

        if (e->event_id <= 0) return 0;
        if (e->objective_index < 1 || e->objective_index > 3) return 0;
        if (e->metric < CAMPAIGN_METRIC_PLACEMENT ||
            e->metric > CAMPAIGN_METRIC_NITRO_NORMAL) return 0;
        if (e->compare < CAMPAIGN_COMPARE_LE ||
            e->compare > CAMPAIGN_COMPARE_EQ) return 0;
        if (e->threshold < 0) return 0;
        if (e->stars < 0 || e->stars > 3) return 0;

        if (i > 0) {
            const CampaignObjectiveDefinition* p = &f->entries[i - 1];
            if (CompareKey(e, p->event_id, p->objective_index) <= 0) return 0;
        }
    }
    return 1;
}

int CampaignObjectiveCatalogEnsureLoaded(void) {
    HANDLE h;
    DWORD got = 0;

    if (g_objectives_loaded) return g_objectives.count > 0 ? 1 : 0;

    ZeroBytes(&g_objectives, (uint32_t)sizeof(g_objectives));

    if (!BuildCatalogPath()) {
        InterlockedExchange(&g_objectives_loaded, 1);
        return 0;
    }

    h = CreateFileW(
        g_objectives_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );
    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_objectives_loaded, 1);
        return 0;
    }

    if (!ReadFile(h, &g_objectives, (DWORD)sizeof(g_objectives), &got, 0) ||
        got != (DWORD)sizeof(g_objectives)) {
        CloseHandle(h);
        ZeroBytes(&g_objectives, (uint32_t)sizeof(g_objectives));
        InterlockedExchange(&g_objectives_loaded, 1);
        return 0;
    }
    CloseHandle(h);

    if (!ValidateCatalog(&g_objectives)) {
        ZeroBytes(&g_objectives, (uint32_t)sizeof(g_objectives));
        InterlockedExchange(&g_objectives_loaded, 1);
        return 0;
    }

    InterlockedExchange(&g_objectives_loaded, 1);
    return 1;
}

uint32_t CampaignObjectiveCatalogCount(void) {
    CampaignObjectiveCatalogEnsureLoaded();
    return g_objectives.count;
}

int CampaignObjectiveMetricValue(
    const CampaignRaceMetrics* m,
    int32_t metric,
    int32_t* value
) {
    if (!m || !value) return 0;

    switch (metric) {
    case CAMPAIGN_METRIC_PLACEMENT: *value = m->placement; return 1;
    case CAMPAIGN_METRIC_FINISH_TIME_MS: *value = m->finish_time_ms; return 1;
    case CAMPAIGN_METRIC_DRIFT_METERS: *value = m->drift_meters; return 1;
    case CAMPAIGN_METRIC_AIR_TIME_MS: *value = m->air_time_ms; return 1;
    case CAMPAIGN_METRIC_NITRO_TIME_MS: *value = m->nitro_time_ms; return 1;
    case CAMPAIGN_METRIC_WRECKED_CARS: *value = m->wrecked_cars; return 1;
    case CAMPAIGN_METRIC_WRECKED_ENVIRONMENT: *value = m->wrecked_environment; return 1;
    case CAMPAIGN_METRIC_WRECKS_MADE: *value = m->wrecks_made; return 1;
    case CAMPAIGN_METRIC_FLAT_SPINS: *value = m->flat_spins; return 1;
    case CAMPAIGN_METRIC_BARREL_ROLLS: *value = m->barrel_rolls; return 1;
    case CAMPAIGN_METRIC_OBSTACLES_BROKEN: *value = m->obstacles_broken; return 1;
    case CAMPAIGN_METRIC_NITRO_ALL_IN: *value = m->nitro_all_in; return 1;
    case CAMPAIGN_METRIC_NITRO_CHAIN: *value = m->nitro_chain; return 1;
    case CAMPAIGN_METRIC_NITRO_NORMAL: *value = m->nitro_normal; return 1;
    default: return 0;
    }
}

static int Passes(int32_t value, int32_t compare, int32_t threshold) {
    switch (compare) {
    case CAMPAIGN_COMPARE_LE: return value <= threshold;
    case CAMPAIGN_COMPARE_GE: return value >= threshold;
    case CAMPAIGN_COMPARE_EQ: return value == threshold;
    default: return 0;
    }
}

int CampaignObjectiveEvaluate(
    int32_t event_id,
    const CampaignRaceMetrics* metrics,
    int32_t* stars_out,
    int32_t* achieved_mask_out
) {
    uint32_t i;
    int32_t stars = 0;
    int32_t mask = 0;
    int found = 0;

    if (stars_out) *stars_out = 0;
    if (achieved_mask_out) *achieved_mask_out = 0;

    if (event_id <= 0 || !metrics) return 0;
    if (metrics->size < (uint32_t)sizeof(CampaignRaceMetrics)) return 0;
    if (metrics->version != CAMPAIGN_RACE_METRICS_VERSION) return 0;
    if (metrics->placement <= 0 || metrics->finish_time_ms < 0) return 0;

    if (!CampaignObjectiveCatalogEnsureLoaded()) return 0;

    for (i = 0; i < g_objectives.count; ++i) {
        const CampaignObjectiveDefinition* e = &g_objectives.entries[i];
        int32_t value = 0;

        if (e->event_id < event_id) continue;
        if (e->event_id > event_id) break;

        found = 1;
        if (!CampaignObjectiveMetricValue(metrics, e->metric, &value)) return 0;

        if (Passes(value, e->compare, e->threshold)) {
            stars += e->stars;
            mask |= (1 << (e->objective_index - 1));
        }
    }

    if (!found) return 0;
    if (stars > 3) stars = 3;

    if (stars_out) *stars_out = stars;
    if (achieved_mask_out) *achieved_mask_out = mask;
    return 1;
}
