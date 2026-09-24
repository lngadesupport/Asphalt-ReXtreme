#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignEventCatalog.h"
#include "CampaignSpecialEventCatalog.h"
#include "CampaignSpecialEventState.h"

typedef struct TestEventCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignEventDefinition events[CAMPAIGN_EVENT_CATALOG_MAX_EVENTS];
    uint32_t checksum;
} TestEventCatalogFile;

typedef struct TestSpecialCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignSpecialEventDefinition entries[CAMPAIGN_SPECIAL_EVENT_MAX];
    uint32_t checksum;
} TestSpecialCatalogFile;

static uint32_t Hash(const void* p, uint32_t n) {
    const unsigned char* s = (const unsigned char*)p;
    uint32_t h = 2166136261u;
    uint32_t i;
    for (i = 0; i < n; ++i) {
        h ^= s[i];
        h *= 16777619u;
    }
    return h;
}

static int BuildPath(WCHAR* out, uint32_t cap, const WCHAR* name) {
    DWORD n;
    int i;
    uint32_t p, j = 0;
    n = GetModuleFileNameW(0, out, cap);
    if (n == 0 || n >= cap) return 0;
    i = (int)n - 1;
    while (i >= 0 && out[i] != L'\\' && out[i] != L'/') --i;
    if (i < 0) return 0;
    p = (uint32_t)(i + 1);
    while (name[j]) {
        if (p + 1 >= cap) return 0;
        out[p++] = name[j++];
    }
    out[p] = 0;
    return 1;
}

static int WriteEvents(void) {
    TestEventCatalogFile file;
    WCHAR path[1024];
    HANDLE h;
    DWORD written = 0;
    uint32_t i;
    unsigned char* q = (unsigned char*)&file;

    for (i = 0; i < (uint32_t)sizeof(file); ++i) q[i] = 0;
    file.magic = CAMPAIGN_EVENT_CATALOG_MAGIC;
    file.version = CAMPAIGN_EVENT_CATALOG_VERSION;
    file.count = 3;

    file.events[0].event_id = 1001;
    file.events[0].completion_node_id = 1001;
    file.events[0].max_stars = 3;

    file.events[1].event_id = 1002;
    file.events[1].completion_node_id = 1002;
    file.events[1].max_stars = 3;

    file.events[2].event_id = 1003;
    file.events[2].completion_node_id = 1003;
    file.events[2].max_stars = 3;

    file.checksum = Hash(&file, (uint32_t)sizeof(file) - (uint32_t)sizeof(uint32_t));

    if (!BuildPath(path, 1024, L"CampaignEvents.dat")) return 0;
    h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;
    if (!WriteFile(h, &file, (DWORD)sizeof(file), &written, 0) ||
        written != (DWORD)sizeof(file)) {
        CloseHandle(h);
        DeleteFileW(path);
        return 0;
    }
    FlushFileBuffers(h);
    CloseHandle(h);
    return 1;
}

static int WriteSpecialEvents(void) {
    TestSpecialCatalogFile file;
    WCHAR path[1024];
    HANDLE h;
    DWORD written = 0;
    uint32_t i;
    unsigned char* q = (unsigned char*)&file;

    for (i = 0; i < (uint32_t)sizeof(file); ++i) q[i] = 0;
    file.magic = CAMPAIGN_SPECIAL_EVENT_MAGIC;
    file.version = CAMPAIGN_SPECIAL_EVENT_VERSION;
    file.count = 2;

    file.entries[0].special_event_id = 5001;
    file.entries[0].schedule = CAMPAIGN_SPECIAL_EVENT_WEEKLY;
    file.entries[0].required_node_id = 0;
    file.entries[0].stage_count = 3;
    file.entries[0].start_day_key = 20260101u;
    file.entries[0].end_day_key = 20261231u;
    file.entries[0].stage_event_ids[0] = 1001;
    file.entries[0].stage_event_ids[1] = 1002;
    file.entries[0].stage_event_ids[2] = 1003;

    file.entries[1].special_event_id = 5002;
    file.entries[1].schedule = CAMPAIGN_SPECIAL_EVENT_MANUAL;
    file.entries[1].required_node_id = 0;
    file.entries[1].stage_count = 1;
    file.entries[1].flags = CAMPAIGN_SPECIAL_EVENT_MANUAL_ACTIVE;
    file.entries[1].stage_event_ids[0] = 1003;

    file.checksum = Hash(&file, (uint32_t)sizeof(file) - (uint32_t)sizeof(uint32_t));

    if (!BuildPath(path, 1024, L"CampaignSpecialEvents.dat")) return 0;
    h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;
    if (!WriteFile(h, &file, (DWORD)sizeof(file), &written, 0) ||
        written != (DWORD)sizeof(file)) {
        CloseHandle(h);
        DeleteFileW(path);
        return 0;
    }
    FlushFileBuffers(h);
    CloseHandle(h);
    return 1;
}

static void Cleanup(void) {
    WCHAR path[1024];
    if (BuildPath(path, 1024, L"CampaignEvents.dat")) DeleteFileW(path);
    if (BuildPath(path, 1024, L"CampaignSpecialEvents.dat")) DeleteFileW(path);
    if (BuildPath(path, 1024, L"UserData\\CampaignEdition\\SpecialEventPeriodState.dat")) DeleteFileW(path);
    if (BuildPath(path, 1024, L"UserData\\CampaignEdition\\SpecialEventPeriodState.tmp")) DeleteFileW(path);
}

int main(void) {
    const CampaignSpecialEventDefinition* def;
    uint32_t counts[3];
    uint32_t mask = 0;
    uint32_t completed = 0;

    Cleanup();
    if (!WriteEvents()) return 1;
    if (!WriteSpecialEvents()) return 2;

    if (CampaignEventCatalogCount() != 3) return 3;
    if (CampaignSpecialEventCatalogCount() != 2) return 4;

    def = CampaignSpecialEventCatalogFind(5001);
    if (!def || def->stage_count != 3 ||
        def->stage_event_ids[0] != 1001 ||
        def->stage_event_ids[2] != 1003) return 5;

    if (!CampaignSpecialEventDateAvailable(def, 20260924u)) return 6;
    if (CampaignSpecialEventDateAvailable(def, 20270101u)) return 7;
    if (CampaignSpecialEventPeriodKey(def, 20260924u) != 202639u) return 11;
    if (CampaignSpecialEventPeriodKey(def, 20261001u) != 202640u) return 12;

    if (!CampaignSpecialEventPeriodStateReset()) return 13;
    counts[0] = 5; counts[1] = 2; counts[2] = 0;
    if (!CampaignSpecialEventPeriodStateEvaluate(
            def, 20260924u, counts, 3, &mask, &completed)) return 14;
    if (mask != 0 || completed != 0) return 15;

    counts[0] = 6; counts[1] = 2; counts[2] = 1;
    if (!CampaignSpecialEventPeriodStateEvaluate(
            def, 20260924u, counts, 3, &mask, &completed)) return 16;
    if (mask != 5u || completed != 2u) return 17;

    /* New weekly period snapshots the permanent Career counts as a new baseline. */
    if (!CampaignSpecialEventPeriodStateEvaluate(
            def, 20261001u, counts, 3, &mask, &completed)) return 18;
    if (mask != 0 || completed != 0) return 19;

    counts[1] = 3;
    if (!CampaignSpecialEventPeriodStateEvaluate(
            def, 20261001u, counts, 3, &mask, &completed)) return 20;
    if (mask != 2u || completed != 1u) return 21;

    def = CampaignSpecialEventCatalogFind(5002);
    if (!def || def->schedule != CAMPAIGN_SPECIAL_EVENT_MANUAL) return 8;
    if (!CampaignSpecialEventDateAvailable(def, 20260924u)) return 9;
    if (CampaignSpecialEventPeriodKey(def, 20260924u) != 0) return 22;
    counts[0] = 4;
    if (!CampaignSpecialEventPeriodStateEvaluate(
            def, 20260924u, counts, 1, &mask, &completed)) return 23;
    if (mask != 1u || completed != 1u) return 24;

    if (!CampaignSpecialEventCatalogGet(0) ||
        CampaignSpecialEventCatalogGet(2)) return 10;

    Cleanup();
    return 0;
}
