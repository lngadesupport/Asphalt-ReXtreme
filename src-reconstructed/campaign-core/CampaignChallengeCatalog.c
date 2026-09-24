#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignChallengeCatalog.h"

#define RXCS_MAGIC 0x53435852u /* RXCS */
#define RXCS_VERSION 1u

typedef struct CampaignChallengeCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignChallengeDefinition entries[CAMPAIGN_CHALLENGE_MAX];
    uint32_t checksum;
} CampaignChallengeCatalogFile;

typedef struct CampaignChallengeStateEntry {
    int32_t challenge_id;
    uint32_t period_key;
    int32_t progress;
    uint32_t has_progress;
    uint32_t completed;
    uint32_t claimed;
    uint32_t reserved0;
    uint32_t reserved1;
} CampaignChallengeStateEntry;

typedef struct CampaignChallengeStateFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignChallengeStateEntry entries[CAMPAIGN_CHALLENGE_MAX];
    uint32_t checksum;
} CampaignChallengeStateFile;

static CampaignChallengeCatalogFile g_catalog;
static CampaignChallengeStateFile g_state;
static CampaignChallengeStateFile g_state_load;
static volatile LONG g_catalog_loaded;
static volatile LONG g_state_loaded;
static volatile LONG g_lock;
static WCHAR g_catalog_path[1024];
static WCHAR g_state_dir[1024];
static WCHAR g_state_path[1024];
static WCHAR g_state_tmp[1024];

static void ChallengeZero(void* p, uint32_t n) {
    volatile unsigned char* q = (volatile unsigned char*)p;
    uint32_t i;
    for (i = 0; i < n; ++i) q[i] = 0;
}

static void ChallengeCopy(void* d0, const void* s0, uint32_t n) {
    volatile unsigned char* d = (volatile unsigned char*)d0;
    const volatile unsigned char* s = (const volatile unsigned char*)s0;
    uint32_t i;
    for (i = 0; i < n; ++i) d[i] = s[i];
}

static uint32_t ChallengeHash(const void* p, uint32_t n) {
    const unsigned char* s = (const unsigned char*)p;
    uint32_t h = 2166136261u;
    uint32_t i;
    for (i = 0; i < n; ++i) {
        h ^= s[i];
        h *= 16777619u;
    }
    return h;
}

static void ChallengeLock(void) {
    while (InterlockedCompareExchange(&g_lock, 1, 0) != 0) Sleep(0);
}

static void ChallengeUnlock(void) {
    InterlockedExchange(&g_lock, 0);
}

static int WideAppend(WCHAR* dst, uint32_t cap, const WCHAR* src) {
    uint32_t n = 0, i = 0;
    if (!dst || !src || cap == 0) return 0;
    while (dst[n]) {
        ++n;
        if (n >= cap) return 0;
    }
    while (src[i]) {
        if (n + 1 >= cap) return 0;
        dst[n++] = src[i++];
    }
    dst[n] = 0;
    return 1;
}

static int EnsureDir(const WCHAR* path) {
    DWORD attrs;
    if (!path || !path[0]) return 0;
    attrs = GetFileAttributesW(path);
    if (attrs != INVALID_FILE_ATTRIBUTES) return (attrs & FILE_ATTRIBUTE_DIRECTORY) ? 1 : 0;
    if (CreateDirectoryW(path, 0)) return 1;
    return GetLastError() == ERROR_ALREADY_EXISTS ? 1 : 0;
}

static int BuildPaths(void) {
    WCHAR exe[1024];
    DWORD n;
    int i;

    if (g_catalog_path[0] && g_state_path[0]) return 1;
    ChallengeZero(exe, (uint32_t)sizeof(exe));
    n = GetModuleFileNameW(0, exe, 1024);
    if (n == 0 || n >= 1024) return 0;
    i = (int)n - 1;
    while (i >= 0 && exe[i] != L'\\' && exe[i] != L'/') --i;
    if (i < 0) return 0;
    exe[i + 1] = 0;

    ChallengeZero(g_catalog_path, (uint32_t)sizeof(g_catalog_path));
    ChallengeZero(g_state_dir, (uint32_t)sizeof(g_state_dir));
    ChallengeZero(g_state_path, (uint32_t)sizeof(g_state_path));
    ChallengeZero(g_state_tmp, (uint32_t)sizeof(g_state_tmp));

    if (!WideAppend(g_catalog_path, 1024, exe) ||
        !WideAppend(g_catalog_path, 1024, L"CampaignChallenges.dat")) return 0;

    if (!WideAppend(g_state_dir, 1024, exe) ||
        !WideAppend(g_state_dir, 1024, L"UserData")) return 0;
    if (!EnsureDir(g_state_dir)) return 0;
    if (!WideAppend(g_state_dir, 1024, L"\\CampaignEdition")) return 0;
    if (!EnsureDir(g_state_dir)) return 0;

    if (!WideAppend(g_state_path, 1024, g_state_dir) ||
        !WideAppend(g_state_path, 1024, L"\\ChallengeState.dat")) return 0;
    if (!WideAppend(g_state_tmp, 1024, g_state_dir) ||
        !WideAppend(g_state_tmp, 1024, L"\\ChallengeState.tmp")) return 0;
    return 1;
}

static uint32_t CatalogChecksum(const CampaignChallengeCatalogFile* f) {
    return ChallengeHash(f, (uint32_t)sizeof(*f) - (uint32_t)sizeof(uint32_t));
}

static uint32_t StateChecksum(const CampaignChallengeStateFile* f) {
    return ChallengeHash(f, (uint32_t)sizeof(*f) - (uint32_t)sizeof(uint32_t));
}

static int DefinitionValid(const CampaignChallengeDefinition* d) {
    if (!d || d->challenge_id <= 0) return 0;
    if (d->scope < CAMPAIGN_CHALLENGE_PERMANENT ||
        d->scope > CAMPAIGN_CHALLENGE_WEEKLY) return 0;
    if (d->metric < CAMPAIGN_METRIC_PLACEMENT ||
        d->metric > CAMPAIGN_METRIC_NITRO_NORMAL) return 0;
    if (d->progress_mode < CAMPAIGN_CHALLENGE_SUM_METRIC ||
        d->progress_mode > CAMPAIGN_CHALLENGE_BEST_MIN) return 0;
    if (d->goal < 0 || d->event_filter_id < 0) return 0;
    if (d->qualifier_compare != 0 &&
        d->qualifier_compare != CAMPAIGN_COMPARE_LE &&
        d->qualifier_compare != CAMPAIGN_COMPARE_GE &&
        d->qualifier_compare != CAMPAIGN_COMPARE_EQ) return 0;
    if (d->reward_credits < 0 || d->reward_premium < 0 ||
        d->reward_item_id < 0 || d->reward_item_amount < 0) return 0;
    if ((d->reward_item_id == 0) != (d->reward_item_amount == 0)) return 0;
    return 1;
}

static int CatalogValid(const CampaignChallengeCatalogFile* f) {
    uint32_t i;
    if (!f || f->magic != CAMPAIGN_CHALLENGE_CATALOG_MAGIC ||
        f->version != CAMPAIGN_CHALLENGE_CATALOG_VERSION ||
        f->count > CAMPAIGN_CHALLENGE_MAX ||
        f->checksum != CatalogChecksum(f)) return 0;
    for (i = 0; i < f->count; ++i) {
        if (!DefinitionValid(&f->entries[i])) return 0;
        if (i > 0 && f->entries[i - 1].challenge_id >= f->entries[i].challenge_id) return 0;
    }
    return 1;
}

int CampaignChallengeCatalogEnsureLoaded(void) {
    HANDLE h;
    DWORD got = 0;

    if (InterlockedCompareExchange(&g_catalog_loaded, 1, 1)) {
        return g_catalog.count > 0 ? 1 : 0;
    }

    ChallengeLock();
    if (g_catalog_loaded) {
        ChallengeUnlock();
        return g_catalog.count > 0 ? 1 : 0;
    }
    ChallengeZero(&g_catalog, (uint32_t)sizeof(g_catalog));

    if (!BuildPaths()) {
        InterlockedExchange(&g_catalog_loaded, 1);
        ChallengeUnlock();
        return 0;
    }

    h = CreateFileW(g_catalog_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                    0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_catalog_loaded, 1);
        ChallengeUnlock();
        return 0;
    }

    if (!ReadFile(h, &g_catalog, (DWORD)sizeof(g_catalog), &got, 0) ||
        got != (DWORD)sizeof(g_catalog)) {
        CloseHandle(h);
        ChallengeZero(&g_catalog, (uint32_t)sizeof(g_catalog));
        InterlockedExchange(&g_catalog_loaded, 1);
        ChallengeUnlock();
        return 0;
    }
    CloseHandle(h);

    if (!CatalogValid(&g_catalog)) {
        ChallengeZero(&g_catalog, (uint32_t)sizeof(g_catalog));
        InterlockedExchange(&g_catalog_loaded, 1);
        ChallengeUnlock();
        return 0;
    }

    InterlockedExchange(&g_catalog_loaded, 1);
    ChallengeUnlock();
    return g_catalog.count > 0 ? 1 : 0;
}

uint32_t CampaignChallengeCatalogCount(void) {
    CampaignChallengeCatalogEnsureLoaded();
    return g_catalog.count;
}

const CampaignChallengeDefinition* CampaignChallengeCatalogGet(uint32_t index) {
    CampaignChallengeCatalogEnsureLoaded();
    if (index >= g_catalog.count) return 0;
    return &g_catalog.entries[index];
}

const CampaignChallengeDefinition* CampaignChallengeCatalogFind(int32_t challenge_id) {
    int lo = 0;
    int hi;
    CampaignChallengeCatalogEnsureLoaded();
    hi = (int)g_catalog.count - 1;
    while (lo <= hi) {
        int mid = lo + ((hi - lo) / 2);
        int32_t id = g_catalog.entries[mid].challenge_id;
        if (id == challenge_id) return &g_catalog.entries[mid];
        if (id < challenge_id) lo = mid + 1;
        else hi = mid - 1;
    }
    return 0;
}

static int IsLeap(int year) {
    if ((year % 400) == 0) return 1;
    if ((year % 100) == 0) return 0;
    return (year % 4) == 0;
}

static uint32_t DayOfYear(const SYSTEMTIME* st) {
    static const uint16_t before_month[12] = {
        0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334
    };
    uint32_t day;
    if (!st || st->wMonth < 1 || st->wMonth > 12 || st->wDay < 1) return 0;
    day = (uint32_t)before_month[st->wMonth - 1] + (uint32_t)st->wDay;
    if (st->wMonth > 2 && IsLeap((int)st->wYear)) ++day;
    return day;
}

static uint32_t PeriodKey(int32_t scope) {
    SYSTEMTIME st;
    uint32_t day;
    GetLocalTime(&st);
    if (scope == CAMPAIGN_CHALLENGE_PERMANENT) return 0;
    if (scope == CAMPAIGN_CHALLENGE_DAILY) {
        return (uint32_t)st.wYear * 10000u +
               (uint32_t)st.wMonth * 100u +
               (uint32_t)st.wDay;
    }
    day = DayOfYear(&st);
    if (scope == CAMPAIGN_CHALLENGE_WEEKLY && day > 0) {
        return (uint32_t)st.wYear * 100u + ((day - 1u) / 7u + 1u);
    }
    return 0;
}

static CampaignChallengeStateEntry* StateFind(int32_t challenge_id) {
    uint32_t i;
    for (i = 0; i < g_state.count; ++i) {
        if (g_state.entries[i].challenge_id == challenge_id) return &g_state.entries[i];
    }
    return 0;
}

static int StateWriteUnlocked(void) {
    HANDLE h;
    DWORD written = 0;
    if (!BuildPaths()) return 0;
    g_state.magic = RXCS_MAGIC;
    g_state.version = RXCS_VERSION;
    g_state.checksum = StateChecksum(&g_state);

    DeleteFileW(g_state_tmp);
    h = CreateFileW(g_state_tmp, GENERIC_WRITE, FILE_SHARE_READ, 0,
                    CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;
    if (!WriteFile(h, &g_state, (DWORD)sizeof(g_state), &written, 0) ||
        written != (DWORD)sizeof(g_state)) {
        CloseHandle(h);
        DeleteFileW(g_state_tmp);
        return 0;
    }
    FlushFileBuffers(h);
    CloseHandle(h);
    if (!MoveFileExW(g_state_tmp, g_state_path,
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(g_state_tmp);
        return 0;
    }
    return 1;
}

static int SyncDefinitionsUnlocked(int* changed) {
    uint32_t i;
    if (changed) *changed = 0;
    if (!CampaignChallengeCatalogEnsureLoaded()) return 0;

    for (i = 0; i < g_catalog.count; ++i) {
        const CampaignChallengeDefinition* d = &g_catalog.entries[i];
        CampaignChallengeStateEntry* e = StateFind(d->challenge_id);
        uint32_t key = PeriodKey(d->scope);

        if (!e) {
            if (g_state.count >= CAMPAIGN_CHALLENGE_MAX) return 0;
            e = &g_state.entries[g_state.count++];
            ChallengeZero(e, (uint32_t)sizeof(*e));
            e->challenge_id = d->challenge_id;
            e->period_key = key;
            if (changed) *changed = 1;
        } else if (e->period_key != key) {
            int32_t id = e->challenge_id;
            ChallengeZero(e, (uint32_t)sizeof(*e));
            e->challenge_id = id;
            e->period_key = key;
            if (changed) *changed = 1;
        }
    }
    return 1;
}

static int StateFileValid(const CampaignChallengeStateFile* f) {
    uint32_t i, j;
    if (!f || f->magic != RXCS_MAGIC || f->version != RXCS_VERSION ||
        f->count > CAMPAIGN_CHALLENGE_MAX ||
        f->checksum != StateChecksum(f)) return 0;
    for (i = 0; i < f->count; ++i) {
        if (f->entries[i].challenge_id <= 0 ||
            f->entries[i].has_progress > 1 ||
            f->entries[i].completed > 1 ||
            f->entries[i].claimed > 1 ||
            (f->entries[i].claimed && !f->entries[i].completed)) return 0;
        for (j = 0; j < i; ++j) {
            if (f->entries[i].challenge_id == f->entries[j].challenge_id) return 0;
        }
    }
    return 1;
}

int CampaignChallengesEnsureLoaded(void) {
    HANDLE h;
    DWORD got = 0;
    int changed = 0;

    if (InterlockedCompareExchange(&g_state_loaded, 1, 1)) return 1;
    if (!CampaignChallengeCatalogEnsureLoaded()) return 0;

    ChallengeLock();
    if (g_state_loaded) {
        ChallengeUnlock();
        return 1;
    }

    ChallengeZero(&g_state, (uint32_t)sizeof(g_state));
    ChallengeZero(&g_state_load, (uint32_t)sizeof(g_state_load));
    g_state.magic = RXCS_MAGIC;
    g_state.version = RXCS_VERSION;

    if (!BuildPaths()) {
        ChallengeUnlock();
        return 0;
    }

    h = CreateFileW(g_state_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                    0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h != INVALID_HANDLE_VALUE) {
        if (ReadFile(h, &g_state_load, (DWORD)sizeof(g_state_load), &got, 0) &&
            got == (DWORD)sizeof(g_state_load) &&
            StateFileValid(&g_state_load)) {
            ChallengeCopy(&g_state, &g_state_load, (uint32_t)sizeof(g_state));
        }
        CloseHandle(h);
    }

    if (!SyncDefinitionsUnlocked(&changed)) {
        ChallengeUnlock();
        return 0;
    }
    InterlockedExchange(&g_state_loaded, 1);

    if (changed || GetFileAttributesW(g_state_path) == INVALID_FILE_ATTRIBUTES) {
        if (!StateWriteUnlocked()) {
            ChallengeUnlock();
            return 0;
        }
    }

    ChallengeUnlock();
    return 1;
}

int CampaignChallengesRefreshPeriods(void) {
    int changed = 0;
    int result = 1;
    if (!CampaignChallengesEnsureLoaded()) return 0;
    ChallengeLock();
    if (!SyncDefinitionsUnlocked(&changed)) result = 0;
    else if (changed) result = StateWriteUnlocked();
    ChallengeUnlock();
    return result;
}

static int Passes(int32_t value, int32_t compare, int32_t threshold) {
    if (compare == 0) return 1;
    if (compare == CAMPAIGN_COMPARE_LE) return value <= threshold;
    if (compare == CAMPAIGN_COMPARE_GE) return value >= threshold;
    if (compare == CAMPAIGN_COMPARE_EQ) return value == threshold;
    return 0;
}

static int AddSaturating(int32_t a, int32_t b, int32_t* out) {
    if (!out || b < 0) return 0;
    if (a > 0x7FFFFFFF - b) *out = 0x7FFFFFFF;
    else *out = a + b;
    return 1;
}

static void UpdateCompletion(
    const CampaignChallengeDefinition* d,
    CampaignChallengeStateEntry* e
) {
    if (!d || !e || !e->has_progress) return;
    if (d->progress_mode == CAMPAIGN_CHALLENGE_BEST_MIN) {
        if (e->progress <= d->goal) e->completed = 1;
    } else if (e->progress >= d->goal) {
        e->completed = 1;
    }
}

int CampaignChallengesOnRace(int32_t event_id, const CampaignRaceMetrics* metrics) {
    uint32_t i;
    int changed = 0;
    int32_t value;

    if (event_id <= 0 || !metrics ||
        metrics->size < (uint32_t)sizeof(*metrics) ||
        metrics->version != CAMPAIGN_RACE_METRICS_VERSION) return 0;
    if (!CampaignChallengesEnsureLoaded() || !CampaignChallengesRefreshPeriods()) return 0;

    ChallengeLock();
    for (i = 0; i < g_catalog.count; ++i) {
        const CampaignChallengeDefinition* d = &g_catalog.entries[i];
        CampaignChallengeStateEntry* e;
        int32_t next;

        if (d->event_filter_id > 0 && d->event_filter_id != event_id) continue;
        if (!CampaignObjectiveMetricValue(metrics, d->metric, &value)) continue;
        if (!Passes(value, d->qualifier_compare, d->qualifier_threshold)) continue;

        e = StateFind(d->challenge_id);
        if (!e || e->claimed) continue;

        switch (d->progress_mode) {
        case CAMPAIGN_CHALLENGE_SUM_METRIC:
            if (value < 0 || !AddSaturating(e->progress, value, &next)) continue;
            e->progress = next;
            e->has_progress = 1;
            changed = 1;
            break;
        case CAMPAIGN_CHALLENGE_COUNT_MATCHES:
            if (!AddSaturating(e->progress, 1, &next)) continue;
            e->progress = next;
            e->has_progress = 1;
            changed = 1;
            break;
        case CAMPAIGN_CHALLENGE_BEST_MAX:
            if (!e->has_progress || value > e->progress) {
                e->progress = value;
                e->has_progress = 1;
                changed = 1;
            }
            break;
        case CAMPAIGN_CHALLENGE_BEST_MIN:
            if (!e->has_progress || value < e->progress) {
                e->progress = value;
                e->has_progress = 1;
                changed = 1;
            }
            break;
        default:
            continue;
        }

        UpdateCompletion(d, e);
    }

    if (changed && !StateWriteUnlocked()) {
        ChallengeUnlock();
        return 0;
    }
    ChallengeUnlock();
    return 1;
}

static int FillStatus(
    const CampaignChallengeDefinition* d,
    const CampaignChallengeStateEntry* e,
    CampaignChallengeStatus* out
) {
    if (!d || !e || !out || out->size < (uint32_t)sizeof(*out)) return 0;
    out->size = (uint32_t)sizeof(*out);
    out->challenge_id = d->challenge_id;
    out->scope = d->scope;
    out->metric = d->metric;
    out->progress_mode = d->progress_mode;
    out->goal = d->goal;
    out->progress = e->progress;
    out->has_progress = e->has_progress;
    out->completed = e->completed;
    out->claimed = e->claimed;
    out->period_key = e->period_key;
    out->reward_credits = d->reward_credits;
    out->reward_premium = d->reward_premium;
    out->reward_item_id = d->reward_item_id;
    out->reward_item_amount = d->reward_item_amount;
    return 1;
}

int CampaignChallengesGetStatus(int32_t challenge_id, CampaignChallengeStatus* out) {
    const CampaignChallengeDefinition* d;
    CampaignChallengeStateEntry* e;
    int result;
    if (!out || out->size < (uint32_t)sizeof(*out)) return 0;
    if (!CampaignChallengesEnsureLoaded() || !CampaignChallengesRefreshPeriods()) return 0;
    ChallengeLock();
    d = CampaignChallengeCatalogFind(challenge_id);
    e = StateFind(challenge_id);
    result = FillStatus(d, e, out);
    ChallengeUnlock();
    return result;
}

int CampaignChallengesGetStatusByIndex(uint32_t index, CampaignChallengeStatus* out) {
    const CampaignChallengeDefinition* d;
    CampaignChallengeStateEntry* e;
    int result;
    if (!out || out->size < (uint32_t)sizeof(*out)) return 0;
    if (!CampaignChallengesEnsureLoaded() || !CampaignChallengesRefreshPeriods()) return 0;
    ChallengeLock();
    d = CampaignChallengeCatalogGet(index);
    e = d ? StateFind(d->challenge_id) : 0;
    result = FillStatus(d, e, out);
    ChallengeUnlock();
    return result;
}

int CampaignChallengesCanClaim(int32_t challenge_id, CampaignChallengeStatus* out) {
    CampaignChallengeStatus temp;
    CampaignChallengeStatus* target = out ? out : &temp;
    ChallengeZero(target, (uint32_t)sizeof(*target));
    target->size = (uint32_t)sizeof(*target);
    if (!CampaignChallengesGetStatus(challenge_id, target)) return 0;
    return target->completed && !target->claimed ? 1 : 0;
}

int CampaignChallengesMarkClaimed(int32_t challenge_id) {
    CampaignChallengeStateEntry* e;
    int result = 0;
    if (!CampaignChallengesEnsureLoaded() || !CampaignChallengesRefreshPeriods()) return 0;
    ChallengeLock();
    e = StateFind(challenge_id);
    if (e && e->completed && !e->claimed) {
        e->claimed = 1;
        result = StateWriteUnlocked();
        if (!result) e->claimed = 0;
    }
    ChallengeUnlock();
    return result;
}

int CampaignChallengesResetState(void) {
    int result;
    ChallengeLock();
    ChallengeZero(&g_state, (uint32_t)sizeof(g_state));
    ChallengeZero(&g_state_load, (uint32_t)sizeof(g_state_load));
    InterlockedExchange(&g_state_loaded, 0);
    if (!BuildPaths()) {
        ChallengeUnlock();
        return 0;
    }
    result = DeleteFileW(g_state_path) || GetLastError() == ERROR_FILE_NOT_FOUND;
    DeleteFileW(g_state_tmp);
    ChallengeUnlock();
    return result ? 1 : 0;
}
