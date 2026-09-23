#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignCore.h"
#include "CampaignCatalog.h"
#include "CampaignEventCatalog.h"
#include "CampaignObjectiveCatalog.h"
#include "CampaignUpgradeCatalog.h"
#include "CampaignUpgradeUiMap.h"
#include "CampaignStoreCatalog.h"

#define CAMPAIGN_MAGIC 0x32435852u /* RXC2 */
#define CAMPAIGN_VERSION 3u

#define CAMPAIGN_MAX_OWNED 256u
#define CAMPAIGN_MAX_INVENTORY 512u
#define CAMPAIGN_MAX_VEHICLE_PARTS 768u
#define CAMPAIGN_MAX_PROGRESS 512u
#define CAMPAIGN_MAX_EVENT_STATE 512u

#define CAMPAIGN_DEFAULT_CREDITS 50000
#define CAMPAIGN_DEFAULT_PREMIUM 0

#define CAMPAIGN_RACE_SESSION_MAGIC 0x53525852u /* RXRS */
#define CAMPAIGN_RACE_SESSION_VERSION 1u

typedef struct CampaignInventoryEntry {
    int32_t item_id;
    int32_t amount;
} CampaignInventoryEntry;

typedef struct CampaignVehiclePartEntry {
    int32_t car_id;
    int16_t slot;
    int16_t level;
} CampaignVehiclePartEntry;

typedef struct CampaignProgressEntry {
    int32_t node_id;
    int16_t state;
    int16_t stars;
    int32_t best_time_ms;
} CampaignProgressEntry;

typedef struct CampaignEventStateEntry {
    int32_t event_id;
    uint32_t completion_count;
    int16_t best_position;
    int16_t best_stars;
    int32_t best_time_ms;
} CampaignEventStateEntry;

typedef struct CampaignRaceSession {
    uint32_t magic;
    uint32_t version;
    uint32_t session_id;
    int32_t event_id;
    int32_t car_id;
    uint32_t start_revision;
    uint32_t checksum;
} CampaignRaceSession;

typedef struct CampaignStateV3 {
    uint32_t magic;
    uint32_t version;
    uint32_t revision;
    uint32_t flags;

    int32_t credits;
    int32_t premium_currency;
    int32_t selected_car_id;
    int32_t last_acquired_car_id;

    uint32_t craft_count;
    uint32_t race_count;
    uint32_t total_stars;
    uint32_t last_completed_race_session_id;

    uint32_t owned_count;
    int32_t owned_car_ids[CAMPAIGN_MAX_OWNED];

    uint32_t inventory_count;
    CampaignInventoryEntry inventory[CAMPAIGN_MAX_INVENTORY];

    uint32_t upgrade_count;
    CampaignVehiclePartEntry upgrades[CAMPAIGN_MAX_VEHICLE_PARTS];

    uint32_t prokit_count;
    CampaignVehiclePartEntry prokits[CAMPAIGN_MAX_VEHICLE_PARTS];

    uint32_t progress_count;
    CampaignProgressEntry progress[CAMPAIGN_MAX_PROGRESS];

    uint32_t event_state_count;
    CampaignEventStateEntry event_states[CAMPAIGN_MAX_EVENT_STATE];

    uint32_t checksum;
} CampaignStateV3;

/* Exact v2 layout for one-time migration. */
typedef struct CampaignStateV2Legacy {
    uint32_t magic;
    uint32_t version;
    uint32_t revision;
    uint32_t flags;

    int32_t credits;
    int32_t premium_currency;
    int32_t selected_car_id;
    int32_t last_acquired_car_id;

    uint32_t craft_count;
    uint32_t race_count;
    uint32_t total_stars;
    uint32_t reserved0;

    uint32_t owned_count;
    int32_t owned_car_ids[CAMPAIGN_MAX_OWNED];

    uint32_t inventory_count;
    CampaignInventoryEntry inventory[CAMPAIGN_MAX_INVENTORY];

    uint32_t upgrade_count;
    CampaignVehiclePartEntry upgrades[CAMPAIGN_MAX_VEHICLE_PARTS];

    uint32_t prokit_count;
    CampaignVehiclePartEntry prokits[CAMPAIGN_MAX_VEHICLE_PARTS];

    uint32_t progress_count;
    CampaignProgressEntry progress[CAMPAIGN_MAX_PROGRESS];

    uint32_t checksum;
} CampaignStateV2Legacy;

/* Exact v1 layout for one-time migration. */
typedef struct CampaignStateV1 {
    uint32_t magic, version, revision, craft_count;
    int32_t credits, premium_currency, last_car_id;
    uint32_t owned_count;
    int32_t owned_car_ids[256];
    uint32_t inventory_count;
    CampaignInventoryEntry inventory[256];
    uint32_t checksum;
} CampaignStateV1;

#define CAMPAIGN_V1_MAGIC 0x45435852u
#define CAMPAIGN_V1_VERSION 1u

static CampaignStateV3 g_state;
static CampaignStateV3 g_tx_backup;
static CampaignStateV3 g_load_buffer;
static CampaignStateV2Legacy g_v2_buffer;
static CampaignStateV1 g_v1_buffer;
static volatile LONG g_lock;
static volatile LONG g_loaded;

static WCHAR g_campaign_dir[1024];
static WCHAR g_state_path[1024];
static WCHAR g_tmp_path[1024];
static WCHAR g_backup_path[1024];
static WCHAR g_v1_path[1024];
static WCHAR g_v1_archive_path[1024];
static WCHAR g_v2_archive_path[1024];
static WCHAR g_race_session_path[1024];
static WCHAR g_race_session_tmp_path[1024];
static WCHAR g_race_session_consuming_path[1024];
static CampaignRaceSession g_race_session_buffer;

static void LockState(void) {
    while (InterlockedCompareExchange(&g_lock, 1, 0) != 0) Sleep(0);
}

static void UnlockState(void) {
    InterlockedExchange(&g_lock, 0);
}

static void ZeroBytes(void* p, uint32_t count) {
    volatile unsigned char* q = (volatile unsigned char*)p;
    uint32_t i;
    for (i = 0; i < count; ++i) q[i] = 0;
}

static void CopyBytes(void* dst, const void* src, uint32_t count) {
    volatile unsigned char* d = (volatile unsigned char*)dst;
    const volatile unsigned char* s = (const volatile unsigned char*)src;
    uint32_t i;
    for (i = 0; i < count; ++i) d[i] = s[i];
}

static uint32_t WideLen(const WCHAR* s) {
    uint32_t n = 0;
    if (!s) return 0;
    while (s[n]) ++n;
    return n;
}

static int WideAppend(WCHAR* dst, uint32_t cap, const WCHAR* src) {
    uint32_t a = WideLen(dst), b = 0;
    if (!src || a >= cap) return 0;
    while (src[b]) {
        if (a + b + 1 >= cap) return 0;
        dst[a + b] = src[b];
        ++b;
    }
    dst[a + b] = 0;
    return 1;
}

static uint32_t Fnv1a(const unsigned char* data, uint32_t count) {
    uint32_t h = 2166136261u, i;
    for (i = 0; i < count; ++i) {
        h ^= data[i];
        h *= 16777619u;
    }
    return h;
}

static uint32_t StateChecksumV3(const CampaignStateV3* s) {
    return Fnv1a((const unsigned char*)s, (uint32_t)(sizeof(CampaignStateV3) - sizeof(uint32_t)));
}

static uint32_t StateChecksumV2Legacy(const CampaignStateV2Legacy* s) {
    return Fnv1a((const unsigned char*)s, (uint32_t)(sizeof(CampaignStateV2Legacy) - sizeof(uint32_t)));
}

static uint32_t StateChecksumV1(const CampaignStateV1* s) {
    return Fnv1a((const unsigned char*)s, (uint32_t)(sizeof(CampaignStateV1) - sizeof(uint32_t)));
}

static uint32_t RaceSessionChecksum(const CampaignRaceSession* s) {
    return Fnv1a((const unsigned char*)s, (uint32_t)(sizeof(CampaignRaceSession) - sizeof(uint32_t)));
}

static void InitDefaultState(CampaignStateV3* s) {
    ZeroBytes(s, (uint32_t)sizeof(*s));
    s->magic = CAMPAIGN_MAGIC;
    s->version = CAMPAIGN_VERSION;
    s->revision = 1;
    s->credits = CAMPAIGN_DEFAULT_CREDITS;
    s->premium_currency = CAMPAIGN_DEFAULT_PREMIUM;
    s->selected_car_id = -1;
    s->last_acquired_car_id = -1;
    s->checksum = StateChecksumV3(s);
}

static int BuildPaths(void) {
    WCHAR local[512];
    DWORD n;

    ZeroBytes(local, (uint32_t)sizeof(local));
    ZeroBytes(g_campaign_dir, (uint32_t)sizeof(g_campaign_dir));
    ZeroBytes(g_state_path, (uint32_t)sizeof(g_state_path));
    ZeroBytes(g_tmp_path, (uint32_t)sizeof(g_tmp_path));
    ZeroBytes(g_backup_path, (uint32_t)sizeof(g_backup_path));
    ZeroBytes(g_race_session_path, (uint32_t)sizeof(g_race_session_path));
    ZeroBytes(g_race_session_tmp_path, (uint32_t)sizeof(g_race_session_tmp_path));
    ZeroBytes(g_race_session_consuming_path, (uint32_t)sizeof(g_race_session_consuming_path));

    n = GetEnvironmentVariableW(L"LOCALAPPDATA", local, 512);
    if (n == 0 || n >= 512) return 0;

    if (!WideAppend(g_campaign_dir, 1024, local)) return 0;
    if (!WideAppend(g_campaign_dir, 1024, L"\\Packages\\A278AB0D.AsphaltXtreme_h6adky7gbf63m\\LocalState\\CampaignEdition")) return 0;
    CreateDirectoryW(g_campaign_dir, 0);

    if (!WideAppend(g_state_path, 1024, g_campaign_dir)) return 0;
    if (!WideAppend(g_state_path, 1024, L"\\CampaignSave.dat")) return 0;

    if (!WideAppend(g_tmp_path, 1024, g_campaign_dir)) return 0;
    if (!WideAppend(g_tmp_path, 1024, L"\\CampaignSave.tmp")) return 0;

    if (!WideAppend(g_backup_path, 1024, g_campaign_dir)) return 0;
    if (!WideAppend(g_backup_path, 1024, L"\\CampaignSave.bak")) return 0;

    if (!WideAppend(g_race_session_path, 1024, g_campaign_dir)) return 0;
    if (!WideAppend(g_race_session_path, 1024, L"\\CampaignRaceSession.dat")) return 0;

    if (!WideAppend(g_race_session_tmp_path, 1024, g_campaign_dir)) return 0;
    if (!WideAppend(g_race_session_tmp_path, 1024, L"\\CampaignRaceSession.tmp")) return 0;

    if (!WideAppend(g_race_session_consuming_path, 1024, g_campaign_dir)) return 0;
    if (!WideAppend(g_race_session_consuming_path, 1024, L"\\CampaignRaceSession.consuming")) return 0;

    return 1;
}

static int WriteWholeFile(const WCHAR* path, const void* data, DWORD size) {
    HANDLE h;
    DWORD written = 0;

    h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;

    if (!WriteFile(h, data, size, &written, 0) || written != size) {
        CloseHandle(h);
        DeleteFileW(path);
        return 0;
    }

    FlushFileBuffers(h);
    CloseHandle(h);
    return 1;
}

static int IsOwnedUnlocked(int32_t car_id);
static int ProgressGateUnlocked(int32_t node_id);
static int RecordEventUnlocked(
    const CampaignEventDefinition* def,
    int32_t position,
    int32_t stars,
    int32_t finish_time_ms,
    int32_t* credits_awarded,
    int32_t* premium_awarded,
    int32_t* completion_count
);

static int ValidateRaceSession(const CampaignRaceSession* session) {
    if (!session) return 0;
    if (session->magic != CAMPAIGN_RACE_SESSION_MAGIC) return 0;
    if (session->version != CAMPAIGN_RACE_SESSION_VERSION) return 0;
    if (session->session_id == 0 || session->event_id <= 0) return 0;
    if (session->checksum != RaceSessionChecksum(session)) return 0;
    return 1;
}

static int ReadRaceSessionFile(const WCHAR* path, CampaignRaceSession* out) {
    HANDLE h;
    DWORD got = 0;

    if (!path || !out) return 0;
    ZeroBytes(out, (uint32_t)sizeof(*out));

    h = CreateFileW(
        path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );
    if (h == INVALID_HANDLE_VALUE) return 0;

    if (!ReadFile(h, out, (DWORD)sizeof(*out), &got, 0) ||
        got != (DWORD)sizeof(*out)) {
        CloseHandle(h);
        ZeroBytes(out, (uint32_t)sizeof(*out));
        return 0;
    }
    CloseHandle(h);

    if (!ValidateRaceSession(out)) {
        ZeroBytes(out, (uint32_t)sizeof(*out));
        return 0;
    }
    return 1;
}

static int WriteRaceSessionUnlocked(const CampaignRaceSession* source) {
    CampaignRaceSession session;

    if (!source || !g_race_session_path[0]) return 0;
    CopyBytes(&session, source, (uint32_t)sizeof(session));
    session.magic = CAMPAIGN_RACE_SESSION_MAGIC;
    session.version = CAMPAIGN_RACE_SESSION_VERSION;
    session.checksum = RaceSessionChecksum(&session);

    DeleteFileW(g_race_session_tmp_path);
    if (!WriteWholeFile(g_race_session_tmp_path, &session, (DWORD)sizeof(session))) return 0;

    if (!MoveFileExW(
            g_race_session_tmp_path,
            g_race_session_path,
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(g_race_session_tmp_path);
        return 0;
    }
    return 1;
}

static void RecoverConsumingRaceSessionUnlocked(void) {
    CampaignRaceSession* session = &g_race_session_buffer;

    if (!g_race_session_consuming_path[0]) return;
    if (!ReadRaceSessionFile(g_race_session_consuming_path, session)) return;

    if (session->session_id == g_state.last_completed_race_session_id) {
        DeleteFileW(g_race_session_consuming_path);
        return;
    }

    if (GetFileAttributesW(g_race_session_path) == INVALID_FILE_ATTRIBUTES) {
        MoveFileExW(
            g_race_session_consuming_path,
            g_race_session_path,
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
        );
    }
}

static uint32_t NewRaceSessionIdUnlocked(int32_t event_id) {
    uint32_t id;
    id = GetTickCount();
    id ^= (g_state.revision * 2654435761u);
    id ^= ((uint32_t)event_id * 2246822519u);
    id ^= (g_state.race_count * 3266489917u);
    id &= 0x7FFFFFFFu;
    if (id == 0) id = 1;
    if (id == g_state.last_completed_race_session_id) {
        ++id;
        if (id == 0) id = 1;
    }
    return id;
}

static int BeginEventRaceUnlocked(
    int32_t event_id,
    int32_t car_id,
    uint32_t* session_id
) {
    const CampaignEventDefinition* def;
    CampaignRaceSession session;

    if (event_id <= 0) return 0;
    def = CampaignEventCatalogFind(event_id);
    if (!def) return 0;
    if (!ProgressGateUnlocked(def->required_node_id)) return 0;
    if (car_id > 0 && !IsOwnedUnlocked(car_id)) return 0;

    RecoverConsumingRaceSessionUnlocked();

    if (GetFileAttributesW(g_race_session_path) != INVALID_FILE_ATTRIBUTES) {
        return 0;
    }

    ZeroBytes(&session, (uint32_t)sizeof(session));
    session.magic = CAMPAIGN_RACE_SESSION_MAGIC;
    session.version = CAMPAIGN_RACE_SESSION_VERSION;
    session.session_id = NewRaceSessionIdUnlocked(event_id);
    session.event_id = event_id;
    session.car_id = car_id;
    session.start_revision = g_state.revision;
    session.checksum = RaceSessionChecksum(&session);

    if (!WriteRaceSessionUnlocked(&session)) return 0;
    if (session_id) *session_id = session.session_id;
    return 1;
}

static int FinishEventRaceUnlocked(
    uint32_t session_id,
    int32_t position,
    int32_t stars,
    int32_t finish_time_ms,
    int32_t* credits_awarded,
    int32_t* premium_awarded,
    int32_t* completion_count
) {
    CampaignRaceSession* session = &g_race_session_buffer;
    const CampaignEventDefinition* def;

    if (session_id == 0 || position <= 0 || stars < 0 || finish_time_ms < 0) return 0;

    RecoverConsumingRaceSessionUnlocked();

    if (!ReadRaceSessionFile(g_race_session_path, session)) {
        if (session_id == g_state.last_completed_race_session_id) {
            if (credits_awarded) *credits_awarded = 0;
            if (premium_awarded) *premium_awarded = 0;
            if (completion_count) *completion_count = 0;
            return 2;
        }
        return 0;
    }

    if (session->session_id != session_id) return 0;

    def = CampaignEventCatalogFind(session->event_id);
    if (!def) return 0;

    DeleteFileW(g_race_session_consuming_path);
    if (!MoveFileExW(
            g_race_session_path,
            g_race_session_consuming_path,
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        return 0;
    }

    if (!RecordEventUnlocked(
            def,
            position,
            stars,
            finish_time_ms,
            credits_awarded,
            premium_awarded,
            completion_count)) {
        MoveFileExW(
            g_race_session_consuming_path,
            g_race_session_path,
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
        );
        return 0;
    }

    g_state.last_completed_race_session_id = session_id;
    return 1;
}

static int FinishEventRaceMetricsUnlocked(CampaignRaceMetrics* metrics) {
    CampaignRaceSession* session = &g_race_session_buffer;
    int32_t stars = 0;
    int32_t mask = 0;
    int finish_status;

    if (!metrics) return 0;
    if (metrics->size < (uint32_t)sizeof(CampaignRaceMetrics)) return 0;
    if (metrics->version != CAMPAIGN_RACE_METRICS_VERSION) return 0;
    if (metrics->session_id == 0) return 0;

    metrics->stars_awarded = 0;
    metrics->achieved_mask = 0;
    metrics->credits_awarded = 0;
    metrics->premium_awarded = 0;
    metrics->completion_count = 0;

    if (metrics->session_id == g_state.last_completed_race_session_id) {
        return 2;
    }

    RecoverConsumingRaceSessionUnlocked();
    if (!ReadRaceSessionFile(g_race_session_path, session)) return 0;
    if (session->session_id != metrics->session_id) return 0;

    if (!CampaignObjectiveEvaluate(
            session->event_id,
            metrics,
            &stars,
            &mask)) {
        return 0;
    }

    metrics->stars_awarded = stars;
    metrics->achieved_mask = mask;

    finish_status = FinishEventRaceUnlocked(
        metrics->session_id,
        metrics->placement,
        stars,
        metrics->finish_time_ms,
        &metrics->credits_awarded,
        &metrics->premium_awarded,
        &metrics->completion_count
    );

    return finish_status;
}

static int CancelEventRaceUnlocked(uint32_t session_id) {
    CampaignRaceSession* session = &g_race_session_buffer;

    RecoverConsumingRaceSessionUnlocked();
    if (!ReadRaceSessionFile(g_race_session_path, session)) return 1;
    if (session_id != 0 && session->session_id != session_id) return 0;
    return DeleteFileW(g_race_session_path) ? 1 : 0;
}

static int SaveStateUnlocked(void) {
    int had_current;

    if (!g_state_path[0] && !BuildPaths()) return 0;

    g_state.magic = CAMPAIGN_MAGIC;
    g_state.version = CAMPAIGN_VERSION;
    g_state.checksum = StateChecksumV3(&g_state);

    if (!WriteWholeFile(g_tmp_path, &g_state, (DWORD)sizeof(g_state))) return 0;

    had_current = (GetFileAttributesW(g_state_path) != INVALID_FILE_ATTRIBUTES);

    DeleteFileW(g_backup_path);
    if (had_current) {
        if (!MoveFileExW(g_state_path, g_backup_path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
            DeleteFileW(g_tmp_path);
            return 0;
        }
    }

    if (!MoveFileExW(g_tmp_path, g_state_path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        if (had_current) {
            MoveFileExW(g_backup_path, g_state_path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
        }
        DeleteFileW(g_tmp_path);
        return 0;
    }

    return 1;
}

static int ValidateStateV3(const CampaignStateV3* s) {
    if (!s) return 0;
    if (s->magic != CAMPAIGN_MAGIC || s->version != CAMPAIGN_VERSION) return 0;
    if (s->owned_count > CAMPAIGN_MAX_OWNED) return 0;
    if (s->inventory_count > CAMPAIGN_MAX_INVENTORY) return 0;
    if (s->upgrade_count > CAMPAIGN_MAX_VEHICLE_PARTS) return 0;
    if (s->prokit_count > CAMPAIGN_MAX_VEHICLE_PARTS) return 0;
    if (s->progress_count > CAMPAIGN_MAX_PROGRESS) return 0;
    if (s->event_state_count > CAMPAIGN_MAX_EVENT_STATE) return 0;
    if (s->checksum != StateChecksumV3(s)) return 0;
    return 1;
}

static int ValidateStateV2Legacy(const CampaignStateV2Legacy* s) {
    if (!s) return 0;
    if (s->magic != CAMPAIGN_MAGIC || s->version != 2u) return 0;
    if (s->owned_count > CAMPAIGN_MAX_OWNED) return 0;
    if (s->inventory_count > CAMPAIGN_MAX_INVENTORY) return 0;
    if (s->upgrade_count > CAMPAIGN_MAX_VEHICLE_PARTS) return 0;
    if (s->prokit_count > CAMPAIGN_MAX_VEHICLE_PARTS) return 0;
    if (s->progress_count > CAMPAIGN_MAX_PROGRESS) return 0;
    if (s->checksum != StateChecksumV2Legacy(s)) return 0;
    return 1;
}

static int TryLoadV3(const WCHAR* path, CampaignStateV3* out) {
    HANDLE h;
    DWORD got = 0;
    CampaignStateV3* tmp = &g_load_buffer;

    ZeroBytes(tmp, (uint32_t)sizeof(*tmp));

    h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;

    if (!ReadFile(h, tmp, (DWORD)sizeof(*tmp), &got, 0) || got != (DWORD)sizeof(*tmp)) {
        CloseHandle(h);
        return 0;
    }
    CloseHandle(h);

    if (!ValidateStateV3(tmp)) return 0;
    CopyBytes(out, tmp, (uint32_t)sizeof(*tmp));
    return 1;
}

static int TryMigrateV2(void) {
    HANDLE h;
    DWORD got = 0;
    CampaignStateV2Legacy* old = &g_v2_buffer;
    uint32_t i;

    ZeroBytes(old, (uint32_t)sizeof(*old));

    h = CreateFileW(g_state_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;

    if (!ReadFile(h, old, (DWORD)sizeof(*old), &got, 0) || got != (DWORD)sizeof(*old)) {
        CloseHandle(h);
        return 0;
    }
    CloseHandle(h);

    if (!ValidateStateV2Legacy(old)) return 0;

    InitDefaultState(&g_state);
    g_state.revision = old->revision + 1;
    g_state.flags = old->flags;
    g_state.credits = old->credits;
    g_state.premium_currency = old->premium_currency;
    g_state.selected_car_id = old->selected_car_id;
    g_state.last_acquired_car_id = old->last_acquired_car_id;
    g_state.craft_count = old->craft_count;
    g_state.race_count = old->race_count;
    g_state.total_stars = old->total_stars;

    g_state.owned_count = old->owned_count;
    for (i = 0; i < old->owned_count; ++i) g_state.owned_car_ids[i] = old->owned_car_ids[i];

    g_state.inventory_count = old->inventory_count;
    for (i = 0; i < old->inventory_count; ++i) g_state.inventory[i] = old->inventory[i];

    g_state.upgrade_count = old->upgrade_count;
    for (i = 0; i < old->upgrade_count; ++i) g_state.upgrades[i] = old->upgrades[i];

    g_state.prokit_count = old->prokit_count;
    for (i = 0; i < old->prokit_count; ++i) g_state.prokits[i] = old->prokits[i];

    g_state.progress_count = old->progress_count;
    for (i = 0; i < old->progress_count; ++i) g_state.progress[i] = old->progress[i];

    if (!SaveStateUnlocked()) return 0;

    ZeroBytes(g_v2_archive_path, (uint32_t)sizeof(g_v2_archive_path));
    if (WideAppend(g_v2_archive_path, 1024, g_campaign_dir) &&
        WideAppend(g_v2_archive_path, 1024, L"\\CampaignSave.v2.migrated")) {
        DeleteFileW(g_v2_archive_path);
        MoveFileExW(g_backup_path, g_v2_archive_path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
    }
    return 1;
}

static int TryMigrateV1(void) {
    HANDLE h;
    DWORD got = 0;
    CampaignStateV1* old = &g_v1_buffer;
    uint32_t i;

    ZeroBytes(g_v1_path, (uint32_t)sizeof(g_v1_path));
    if (!WideAppend(g_v1_path, 1024, g_campaign_dir)) return 0;
    if (!WideAppend(g_v1_path, 1024, L"\\campaign_state.bin")) return 0;

    ZeroBytes(old, (uint32_t)sizeof(*old));
    h = CreateFileW(g_v1_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;

    if (!ReadFile(h, old, (DWORD)sizeof(*old), &got, 0) || got != (DWORD)sizeof(*old)) {
        CloseHandle(h);
        return 0;
    }
    CloseHandle(h);

    if (old->magic != CAMPAIGN_V1_MAGIC ||
        old->version != CAMPAIGN_V1_VERSION ||
        old->owned_count > 256u ||
        old->inventory_count > 256u ||
        old->checksum != StateChecksumV1(old)) {
        return 0;
    }

    InitDefaultState(&g_state);
    g_state.revision = old->revision + 1;
    g_state.credits = old->credits;
    g_state.premium_currency = old->premium_currency;
    g_state.last_acquired_car_id = old->last_car_id;
    g_state.craft_count = old->craft_count;

    g_state.owned_count = old->owned_count;
    for (i = 0; i < old->owned_count; ++i) g_state.owned_car_ids[i] = old->owned_car_ids[i];

    g_state.inventory_count = old->inventory_count;
    for (i = 0; i < old->inventory_count; ++i) g_state.inventory[i] = old->inventory[i];

    if (!SaveStateUnlocked()) return 0;

    ZeroBytes(g_v1_archive_path, (uint32_t)sizeof(g_v1_archive_path));
    if (WideAppend(g_v1_archive_path, 1024, g_campaign_dir) &&
        WideAppend(g_v1_archive_path, 1024, L"\\campaign_state.v1.migrated")) {
        DeleteFileW(g_v1_archive_path);
        MoveFileExW(g_v1_path, g_v1_archive_path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
    }
    return 1;
}

static void EnsureLoadedUnlocked(void) {
    if (g_loaded) return;

    InitDefaultState(&g_state);
    if (!BuildPaths()) {
        InterlockedExchange(&g_loaded, 1);
        return;
    }

    if (TryLoadV3(g_state_path, &g_state)) {
        InterlockedExchange(&g_loaded, 1);
        return;
    }

    if (TryLoadV3(g_backup_path, &g_state)) {
        SaveStateUnlocked();
        InterlockedExchange(&g_loaded, 1);
        return;
    }

    if (TryMigrateV2()) {
        InterlockedExchange(&g_loaded, 1);
        return;
    }

    if (TryMigrateV1()) {
        InterlockedExchange(&g_loaded, 1);
        return;
    }

    InitDefaultState(&g_state);
    SaveStateUnlocked();
    InterlockedExchange(&g_loaded, 1);
}

static int IsOwnedUnlocked(int32_t car_id) {
    uint32_t i;
    if (car_id <= 0) return 0;
    for (i = 0; i < g_state.owned_count; ++i) {
        if (g_state.owned_car_ids[i] == car_id) return 1;
    }
    return 0;
}

static int AddOwnedNoSave(int32_t car_id) {
    if (car_id <= 0) return 0;
    if (IsOwnedUnlocked(car_id)) return 1;
    if (g_state.owned_count >= CAMPAIGN_MAX_OWNED) return 0;

    g_state.owned_car_ids[g_state.owned_count++] = car_id;
    g_state.last_acquired_car_id = car_id;
    return 1;
}

static int FindInventoryIndex(int32_t item_id) {
    uint32_t i;
    for (i = 0; i < g_state.inventory_count; ++i) {
        if (g_state.inventory[i].item_id == item_id) return (int)i;
    }
    return -1;
}

static int InventoryGetUnlocked(int32_t item_id) {
    int i;
    if (item_id <= 0) return 0;
    i = FindInventoryIndex(item_id);
    return i < 0 ? 0 : g_state.inventory[i].amount;
}

static int InventoryAddNoSave(int32_t item_id, int32_t amount) {
    int i;
    if (item_id <= 0 || amount <= 0) return 0;

    i = FindInventoryIndex(item_id);
    if (i >= 0) {
        if (g_state.inventory[i].amount > 0x7FFFFFFF - amount) return 0;
        g_state.inventory[i].amount += amount;
        return 1;
    }

    if (g_state.inventory_count >= CAMPAIGN_MAX_INVENTORY) return 0;
    g_state.inventory[g_state.inventory_count].item_id = item_id;
    g_state.inventory[g_state.inventory_count].amount = amount;
    ++g_state.inventory_count;
    return 1;
}

static int InventorySpendNoSave(int32_t item_id, int32_t amount) {
    int i;
    if (item_id <= 0 || amount < 0) return 0;
    if (amount == 0) return 1;

    i = FindInventoryIndex(item_id);
    if (i < 0 || g_state.inventory[i].amount < amount) return 0;

    g_state.inventory[i].amount -= amount;
    return 1;
}

static int FindVehiclePartIndex(CampaignVehiclePartEntry* entries, uint32_t count, int32_t car_id, int16_t slot) {
    uint32_t i;
    for (i = 0; i < count; ++i) {
        if (entries[i].car_id == car_id && entries[i].slot == slot) return (int)i;
    }
    return -1;
}

static int VehiclePartGet(CampaignVehiclePartEntry* entries, uint32_t count, int32_t car_id, int16_t slot) {
    int i = FindVehiclePartIndex(entries, count, car_id, slot);
    return i < 0 ? 0 : entries[i].level;
}

static int VehiclePartSet(CampaignVehiclePartEntry* entries, uint32_t* count, int32_t car_id, int16_t slot, int16_t level) {
    int i;
    if (car_id <= 0 || slot < 0 || level < 0) return 0;

    i = FindVehiclePartIndex(entries, *count, car_id, slot);
    if (i >= 0) {
        entries[i].level = level;
        return 1;
    }

    if (*count >= CAMPAIGN_MAX_VEHICLE_PARTS) return 0;
    entries[*count].car_id = car_id;
    entries[*count].slot = slot;
    entries[*count].level = level;
    ++(*count);
    return 1;
}

static int FindProgressIndex(int32_t node_id) {
    uint32_t i;
    for (i = 0; i < g_state.progress_count; ++i) {
        if (g_state.progress[i].node_id == node_id) return (int)i;
    }
    return -1;
}

static CampaignProgressEntry* GetOrCreateProgress(int32_t node_id) {
    int i;
    if (node_id <= 0) return 0;

    i = FindProgressIndex(node_id);
    if (i >= 0) return &g_state.progress[i];

    if (g_state.progress_count >= CAMPAIGN_MAX_PROGRESS) return 0;
    i = (int)g_state.progress_count++;
    g_state.progress[i].node_id = node_id;
    g_state.progress[i].state = 0;
    g_state.progress[i].stars = 0;
    g_state.progress[i].best_time_ms = 0;
    return &g_state.progress[i];
}

static int ProgressGateUnlocked(int32_t node_id) {
    int i;
    if (node_id <= 0) return 1;
    i = FindProgressIndex(node_id);
    if (i < 0) return 0;
    return g_state.progress[i].state > 0 ? 1 : 0;
}

static int FindEventStateIndex(int32_t event_id) {
    uint32_t i;
    for (i = 0; i < g_state.event_state_count; ++i) {
        if (g_state.event_states[i].event_id == event_id) return (int)i;
    }
    return -1;
}

static CampaignEventStateEntry* GetOrCreateEventState(int32_t event_id) {
    int i;
    if (event_id <= 0) return 0;

    i = FindEventStateIndex(event_id);
    if (i >= 0) return &g_state.event_states[i];

    if (g_state.event_state_count >= CAMPAIGN_MAX_EVENT_STATE) return 0;

    i = (int)g_state.event_state_count++;
    g_state.event_states[i].event_id = event_id;
    g_state.event_states[i].completion_count = 0;
    g_state.event_states[i].best_position = 0;
    g_state.event_states[i].best_stars = 0;
    g_state.event_states[i].best_time_ms = 0;
    return &g_state.event_states[i];
}

static int32_t RepeatMultiplierPermille(uint32_t completion_count) {
    uint32_t after_grace;
    int32_t value;

    if (completion_count <= 10u) return 1000;

    after_grace = completion_count - 10u;
    if (after_grace >= 10u) return 980;

    value = 1000 - (int32_t)(after_grace * 2u);
    if (value < 980) value = 980;
    return value;
}

static int32_t ScaleReward(int32_t amount, int32_t permille) {
    int32_t whole;
    int32_t remainder;
    int32_t scaled;

    if (amount <= 0 || permille <= 0) return 0;
    if (permille > 1000) permille = 1000;

    whole = amount / 1000;
    remainder = amount % 1000;

    /* Overflow-safe because whole*permille <= amount and remainder < 1000. */
    scaled = whole * permille;
    scaled += ((remainder * permille) + 500) / 1000;
    return scaled;
}

static int RecordEventUnlocked(
    const CampaignEventDefinition* def,
    int32_t position,
    int32_t stars,
    int32_t finish_time_ms,
    int32_t* credits_awarded,
    int32_t* premium_awarded,
    int32_t* completion_count
) {
    CampaignEventStateEntry* state;
    CampaignProgressEntry* progress = 0;
    int32_t placement_bonus = 0;
    int32_t multiplier;
    int32_t credits;
    int32_t premium;
    int32_t capped_stars;
    int32_t previous_stars = 0;

    if (!def || def->event_id <= 0) return 0;
    if (position <= 0) return 0;
    if (stars < 0 || finish_time_ms < 0) return 0;
    if (!ProgressGateUnlocked(def->required_node_id)) return 0;

    state = GetOrCreateEventState(def->event_id);
    if (!state) return 0;

    ++state->completion_count;

    if (state->best_position <= 0 || position < state->best_position) {
        state->best_position = (int16_t)position;
    }
    if (finish_time_ms > 0 &&
        (state->best_time_ms <= 0 || finish_time_ms < state->best_time_ms)) {
        state->best_time_ms = finish_time_ms;
    }

    capped_stars = stars;
    if (capped_stars > def->max_stars) capped_stars = def->max_stars;
    if (capped_stars < 0) capped_stars = 0;

    if (def->completion_node_id > 0) {
        progress = GetOrCreateProgress(def->completion_node_id);
        if (!progress) return 0;
        previous_stars = progress->stars;
        progress->state = 1;
        if (capped_stars > progress->stars) progress->stars = (int16_t)capped_stars;
        if (finish_time_ms > 0 &&
            (progress->best_time_ms <= 0 || finish_time_ms < progress->best_time_ms)) {
            progress->best_time_ms = finish_time_ms;
        }
    } else {
        previous_stars = state->best_stars;
    }

    if (capped_stars > state->best_stars) state->best_stars = (int16_t)capped_stars;
    if (capped_stars > previous_stars) {
        g_state.total_stars += (uint32_t)(capped_stars - previous_stars);
    }

    switch (position) {
    case 1: placement_bonus = def->position1_credits; break;
    case 2: placement_bonus = def->position2_credits; break;
    case 3: placement_bonus = def->position3_credits; break;
    default: placement_bonus = 0; break;
    }

    multiplier = RepeatMultiplierPermille(state->completion_count);
    if (def->participation_credits > 0x7FFFFFFF - placement_bonus) return 0;
    credits = ScaleReward(def->participation_credits + placement_bonus, multiplier);
    premium = ScaleReward(def->premium_reward, multiplier);

    if (g_state.credits > 0x7FFFFFFF - credits) return 0;
    if (g_state.premium_currency > 0x7FFFFFFF - premium) return 0;

    g_state.credits += credits;
    g_state.premium_currency += premium;
    ++g_state.race_count;

    if (credits_awarded) *credits_awarded = credits;
    if (premium_awarded) *premium_awarded = premium;
    if (completion_count) *completion_count = (int32_t)state->completion_count;
    return 1;
}

static int SpendUpgradeCostUnlocked(
    const CampaignUpgradeDefinition* def,
    int32_t* before_value,
    int32_t* after_value
) {
    if (!def || def->cost < 0) return 0;

    if (before_value) *before_value = 0;
    if (after_value) *after_value = 0;

    switch (def->cost_type) {
    case CAMPAIGN_COST_CREDITS:
        if (g_state.credits < def->cost) return 0;
        if (before_value) *before_value = g_state.credits;
        g_state.credits -= def->cost;
        if (after_value) *after_value = g_state.credits;
        return 1;

    case CAMPAIGN_COST_PREMIUM:
        if (g_state.premium_currency < def->cost) return 0;
        if (before_value) *before_value = g_state.premium_currency;
        g_state.premium_currency -= def->cost;
        if (after_value) *after_value = g_state.premium_currency;
        return 1;

    case CAMPAIGN_COST_INVENTORY:
        if (before_value) *before_value = InventoryGetUnlocked(def->item_id);
        if (!InventorySpendNoSave(def->item_id, def->cost)) return 0;
        if (after_value) *after_value = InventoryGetUnlocked(def->item_id);
        return 1;

    case CAMPAIGN_COST_FREE:
        return 1;

    default:
        return 0;
    }
}

static int ApplyUpgradeDefinitionUnlocked(
    const CampaignUpgradeDefinition* def,
    int32_t* before_value,
    int32_t* after_value
) {
    CampaignVehiclePartEntry* entries;
    uint32_t* count;
    int current;

    if (!def || def->car_id <= 0 || def->part_slot < 0 || def->target_level <= 0) return 0;
    if (!IsOwnedUnlocked(def->car_id)) return 0;
    if (!ProgressGateUnlocked(def->unlock_node_id)) return 0;

    if (def->kind == CAMPAIGN_UPGRADE_KIND_STANDARD) {
        entries = g_state.upgrades;
        count = &g_state.upgrade_count;
    } else if (def->kind == CAMPAIGN_UPGRADE_KIND_PROKIT) {
        entries = g_state.prokits;
        count = &g_state.prokit_count;
    } else {
        return 0;
    }

    current = VehiclePartGet(entries, *count, def->car_id, (int16_t)def->part_slot);

    if (current >= def->target_level) {
        if (before_value) *before_value = 0;
        if (after_value) *after_value = 0;
        return 1;
    }

    if (current + 1 != def->target_level) return 0;
    if (!SpendUpgradeCostUnlocked(def, before_value, after_value)) return 0;

    return VehiclePartSet(
        entries,
        count,
        def->car_id,
        (int16_t)def->part_slot,
        (int16_t)def->target_level
    );
}

static int ApplyUpgradeUiActionUnlocked(
    int32_t car_id,
    int32_t ui_action_id,
    int32_t* target_level,
    int32_t* before_value,
    int32_t* after_value
) {
    const CampaignUpgradeUiEntry* map;
    const CampaignUpgradeDefinition* def;
    CampaignVehiclePartEntry* entries;
    uint32_t count;
    int current;
    int next;

    if (car_id <= 0 || ui_action_id <= 0) return 0;

    map = CampaignUpgradeUiMapFind(ui_action_id);
    if (!map) return 0;

    if (map->kind == CAMPAIGN_UPGRADE_KIND_STANDARD) {
        entries = g_state.upgrades;
        count = g_state.upgrade_count;
    } else if (map->kind == CAMPAIGN_UPGRADE_KIND_PROKIT) {
        entries = g_state.prokits;
        count = g_state.prokit_count;
    } else {
        return 0;
    }

    current = VehiclePartGet(entries, count, car_id, (int16_t)map->part_slot);
    if (current < 0 || current >= 0x7FFF) return 0;
    next = current + 1;

    def = CampaignUpgradeCatalogFind(
        car_id,
        map->kind,
        map->part_slot,
        next
    );
    if (!def) return 0;

    if (!ApplyUpgradeDefinitionUnlocked(def, before_value, after_value)) return 0;
    if (target_level) *target_level = next;
    return 1;
}

static int AcquireCatalogRecipeUnlocked(
    const CampaignVehicleRecipe* recipe,
    int32_t* before_value,
    int32_t* after_value
) {
    if (!recipe || recipe->car_id <= 0 || recipe->cost < 0) return 0;
    if (!ProgressGateUnlocked(recipe->unlock_node_id)) return 0;

    if (IsOwnedUnlocked(recipe->car_id)) {
        if (before_value) *before_value = 0;
        if (after_value) *after_value = 0;
        return 1;
    }

    if (before_value) *before_value = 0;
    if (after_value) *after_value = 0;

    switch (recipe->acquisition_type) {
    case CAMPAIGN_ACQUIRE_BLUEPRINT:
        if (before_value) *before_value = InventoryGetUnlocked(recipe->item_id);
        if (!InventorySpendNoSave(recipe->item_id, recipe->cost)) return 0;
        if (after_value) *after_value = InventoryGetUnlocked(recipe->item_id);
        break;

    case CAMPAIGN_ACQUIRE_CREDITS:
        if (g_state.credits < recipe->cost) return 0;
        if (before_value) *before_value = g_state.credits;
        g_state.credits -= recipe->cost;
        if (after_value) *after_value = g_state.credits;
        break;

    case CAMPAIGN_ACQUIRE_PREMIUM:
        if (g_state.premium_currency < recipe->cost) return 0;
        if (before_value) *before_value = g_state.premium_currency;
        g_state.premium_currency -= recipe->cost;
        if (after_value) *after_value = g_state.premium_currency;
        break;

    case CAMPAIGN_ACQUIRE_FREE:
        break;

    default:
        return 0;
    }

    if (!AddOwnedNoSave(recipe->car_id)) return 0;
    ++g_state.craft_count;
    return 1;
}

static int PurchaseStoreOfferUnlocked(
    const CampaignStoreOffer* offer,
    int32_t* balance_before,
    int32_t* balance_after
) {
    if (!offer || offer->offer_id <= 0 || offer->item_id <= 0 ||
        offer->quantity <= 0 || offer->price < 0) return 0;

    if (!ProgressGateUnlocked(offer->unlock_node_id)) return 0;

    if (balance_before) *balance_before = 0;
    if (balance_after) *balance_after = 0;

    switch (offer->currency_type) {
    case CAMPAIGN_STORE_CURRENCY_CREDITS:
        if (g_state.credits < offer->price) return 0;
        if (balance_before) *balance_before = g_state.credits;
        g_state.credits -= offer->price;
        if (balance_after) *balance_after = g_state.credits;
        break;

    case CAMPAIGN_STORE_CURRENCY_PREMIUM:
        if (g_state.premium_currency < offer->price) return 0;
        if (balance_before) *balance_before = g_state.premium_currency;
        g_state.premium_currency -= offer->price;
        if (balance_after) *balance_after = g_state.premium_currency;
        break;

    case CAMPAIGN_STORE_CURRENCY_FREE:
        if (offer->price != 0) return 0;
        break;

    default:
        return 0;
    }

    return InventoryAddNoSave(offer->item_id, offer->quantity);
}

static int CommitMutationUnlocked(void) {
    ++g_state.revision;
    return SaveStateUnlocked();
}

static int ResolveSelectedCarId(void* garage) {
    unsigned char* gs = (unsigned char*)garage;
    void* holder;
    void* selected;

    if (!gs) return -1;
    holder = *(void**)(gs + 0x2D4);
    if (!holder) return -1;
    selected = *(void**)holder;
    if (!selected) return -1;

    /*
      UI adapter only.  The selected vehicle object exposes its stable car id
      at +0xC0 in this build.  Campaign logic does not trust any ownership,
      economy or CraftCar state from the object.
    */
    return *(int32_t*)((unsigned char*)selected + 0xC0);
}

extern void __cdecl CampaignInvokeGarageUi(void* widget);

static void RefreshGarageUi(void* garage) {
    unsigned char* gs = (unsigned char*)garage;
    void* widget;

    if (!gs) return;
    widget = *(void**)(gs + 0x35C);
    if (!widget) return;
    CampaignInvokeGarageUi(widget);
}

int __cdecl CampaignIsOwned(int32_t car_id) {
    int result;
    LockState();
    EnsureLoadedUnlocked();
    result = IsOwnedUnlocked(car_id);
    UnlockState();
    return result;
}

int __cdecl CampaignCraftInvoke(void* garage) {
    int32_t id = ResolveSelectedCarId(garage);
    const CampaignVehicleRecipe* recipe;
    int ok = 0;

    if (id <= 0) return 0;

    LockState();
    EnsureLoadedUnlocked();

    recipe = CampaignCatalogFind(id);
    if (recipe) {
        CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
        if (AcquireCatalogRecipeUnlocked(recipe, 0, 0)) {
            ok = CommitMutationUnlocked();
        }
        if (!ok) CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
    }

    UnlockState();

    if (ok) RefreshGarageUi(garage);
    return ok;
}

static int ExecuteUnlocked(CampaignCommand* c) {
    CampaignProgressEntry* p;
    int result = 0;

    c->status = 0;
    c->out0 = 0;
    c->out1 = 0;
    c->out2 = 0;
    c->revision = g_state.revision;

    switch (c->op) {
    case CAMPAIGN_OP_GET_CREDITS:
        c->out0 = g_state.credits;
        c->status = 1;
        return 1;

    case CAMPAIGN_OP_ADD_CREDITS:
        if (c->a <= 0 || g_state.credits > 0x7FFFFFFF - c->a) return 0;
        CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
        g_state.credits += c->a;
        result = CommitMutationUnlocked();
        break;

    case CAMPAIGN_OP_SPEND_CREDITS:
        if (c->a < 0 || g_state.credits < c->a) return 0;
        CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
        g_state.credits -= c->a;
        result = CommitMutationUnlocked();
        break;

    case CAMPAIGN_OP_GET_PREMIUM:
        c->out0 = g_state.premium_currency;
        c->status = 1;
        return 1;

    case CAMPAIGN_OP_ADD_PREMIUM:
        if (c->a <= 0 || g_state.premium_currency > 0x7FFFFFFF - c->a) return 0;
        CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
        g_state.premium_currency += c->a;
        result = CommitMutationUnlocked();
        break;

    case CAMPAIGN_OP_SPEND_PREMIUM:
        if (c->a < 0 || g_state.premium_currency < c->a) return 0;
        CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
        g_state.premium_currency -= c->a;
        result = CommitMutationUnlocked();
        break;

    case CAMPAIGN_OP_INVENTORY_GET:
        c->out0 = InventoryGetUnlocked(c->a);
        c->status = 1;
        return 1;

    case CAMPAIGN_OP_INVENTORY_ADD:
        CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
        if (!InventoryAddNoSave(c->a, c->b)) return 0;
        result = CommitMutationUnlocked();
        break;

    case CAMPAIGN_OP_INVENTORY_SPEND:
        CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
        if (!InventorySpendNoSave(c->a, c->b)) return 0;
        result = CommitMutationUnlocked();
        break;

    case CAMPAIGN_OP_IS_OWNED:
        c->out0 = IsOwnedUnlocked(c->a);
        c->status = 1;
        return 1;

    case CAMPAIGN_OP_ACQUIRE_CAR:
        CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
        if (!AddOwnedNoSave(c->a)) return 0;
        result = CommitMutationUnlocked();
        break;

    case CAMPAIGN_OP_CRAFT_CAR:
        /*
          a = car_id
          b = blueprint/item id
          c = required amount
        */
        if (c->a <= 0 || c->b <= 0 || c->c < 0) return 0;
        if (IsOwnedUnlocked(c->a)) {
            c->status = 1;
            c->out0 = 1;
            return 1;
        }

        CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
        c->out1 = InventoryGetUnlocked(c->b);
        if (!InventorySpendNoSave(c->b, c->c) || !AddOwnedNoSave(c->a)) return 0;
        ++g_state.craft_count;
        result = CommitMutationUnlocked();
        if (result) {
            c->out0 = 1;
            c->out2 = InventoryGetUnlocked(c->b);
        }
        break;

    case CAMPAIGN_OP_ACQUIRE_CATALOG:
        {
            const CampaignVehicleRecipe* recipe = CampaignCatalogFind(c->a);
            if (!recipe) return 0;

            c->out0 = recipe->acquisition_type;
            CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));

            if (!AcquireCatalogRecipeUnlocked(recipe, &c->out1, &c->out2)) return 0;
            result = CommitMutationUnlocked();
        }
        break;

    case CAMPAIGN_OP_GET_UPGRADE:
        c->out0 = VehiclePartGet(g_state.upgrades, g_state.upgrade_count, c->a, (int16_t)c->b);
        c->status = 1;
        return 1;

    case CAMPAIGN_OP_SET_UPGRADE:
        CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
        if (!VehiclePartSet(g_state.upgrades, &g_state.upgrade_count, c->a, (int16_t)c->b, (int16_t)c->c)) return 0;
        result = CommitMutationUnlocked();
        break;

    case CAMPAIGN_OP_APPLY_UPGRADE:
        {
            const CampaignUpgradeDefinition* def = CampaignUpgradeCatalogFind(
                c->a,
                CAMPAIGN_UPGRADE_KIND_STANDARD,
                c->b,
                c->c
            );
            if (!def) return 0;

            c->out0 = def->target_level;
            CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));

            if (!ApplyUpgradeDefinitionUnlocked(def, &c->out1, &c->out2)) {
                CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
                return 0;
            }
            result = CommitMutationUnlocked();
        }
        break;

    case CAMPAIGN_OP_APPLY_UPGRADE_UI:
        {
            CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));

            if (!ApplyUpgradeUiActionUnlocked(
                    c->a,
                    c->b,
                    &c->out0,
                    &c->out1,
                    &c->out2)) {
                CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
                return 0;
            }

            result = CommitMutationUnlocked();
        }
        break;

    case CAMPAIGN_OP_GET_PROKIT:
        c->out0 = VehiclePartGet(g_state.prokits, g_state.prokit_count, c->a, (int16_t)c->b);
        c->status = 1;
        return 1;

    case CAMPAIGN_OP_SET_PROKIT:
        CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
        if (!VehiclePartSet(g_state.prokits, &g_state.prokit_count, c->a, (int16_t)c->b, (int16_t)c->c)) return 0;
        result = CommitMutationUnlocked();
        break;

    case CAMPAIGN_OP_APPLY_PROKIT:
        {
            const CampaignUpgradeDefinition* def = CampaignUpgradeCatalogFind(
                c->a,
                CAMPAIGN_UPGRADE_KIND_PROKIT,
                c->b,
                c->c
            );
            if (!def) return 0;

            c->out0 = def->target_level;
            CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));

            if (!ApplyUpgradeDefinitionUnlocked(def, &c->out1, &c->out2)) {
                CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
                return 0;
            }
            result = CommitMutationUnlocked();
        }
        break;

    case CAMPAIGN_OP_GET_PROGRESS:
        p = 0;
        result = FindProgressIndex(c->a);
        if (result >= 0) p = &g_state.progress[result];
        if (p) {
            c->out0 = p->state;
            c->out1 = p->stars;
            c->out2 = p->best_time_ms;
        }
        c->status = 1;
        return 1;

    case CAMPAIGN_OP_SET_PROGRESS:
        CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
        p = GetOrCreateProgress(c->a);
        if (!p) return 0;
        p->state = (int16_t)c->b;
        if (c->c > p->stars) {
            g_state.total_stars += (uint32_t)(c->c - p->stars);
            p->stars = (int16_t)c->c;
        }
        if (c->d > 0 && (p->best_time_ms == 0 || c->d < p->best_time_ms)) p->best_time_ms = c->d;
        result = CommitMutationUnlocked();
        break;

    case CAMPAIGN_OP_RECORD_RACE:
        /*
          a = earned credits
          b = earned premium currency
          c = earned stars
          d = reserved/result flags
        */
        if (c->a < 0 || c->b < 0 || c->c < 0) return 0;
        if (g_state.credits > 0x7FFFFFFF - c->a) return 0;
        if (g_state.premium_currency > 0x7FFFFFFF - c->b) return 0;

        CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
        g_state.credits += c->a;
        g_state.premium_currency += c->b;
        g_state.total_stars += (uint32_t)c->c;
        ++g_state.race_count;
        result = CommitMutationUnlocked();
        break;

    case CAMPAIGN_OP_RECORD_EVENT:
        /*
          a = event_id
          b = placement (1 = first)
          c = stars earned
          d = finish time in milliseconds

          out0 = credits awarded
          out1 = premium currency awarded
          out2 = persistent completion count for this event
        */
        {
            const CampaignEventDefinition* def = CampaignEventCatalogFind(c->a);
            if (!def) return 0;

            CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
            if (!RecordEventUnlocked(def, c->b, c->c, c->d, &c->out0, &c->out1, &c->out2)) {
                CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
                return 0;
            }
            result = CommitMutationUnlocked();
        }
        break;

    case CAMPAIGN_OP_BEGIN_EVENT_RACE:
        {
            uint32_t session_id = 0;
            if (!BeginEventRaceUnlocked(c->a, c->b, &session_id)) return 0;
            c->out0 = (int32_t)session_id;
            c->status = 1;
            return 1;
        }

    case CAMPAIGN_OP_FINISH_EVENT_RACE:
        {
            int finish_status;

            CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
            finish_status = FinishEventRaceUnlocked(
                (uint32_t)c->a,
                c->b,
                c->c,
                c->d,
                &c->out0,
                &c->out1,
                &c->out2
            );

            if (finish_status == 2) {
                c->status = 1;
                c->revision = g_state.revision;
                return 1;
            }
            if (finish_status != 1) {
                CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
                return 0;
            }

            result = CommitMutationUnlocked();
            if (!result) {
                CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
                MoveFileExW(
                    g_race_session_consuming_path,
                    g_race_session_path,
                    MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
                );
                return 0;
            }

            DeleteFileW(g_race_session_consuming_path);
        }
        break;

    case CAMPAIGN_OP_CANCEL_EVENT_RACE:
        if (!CancelEventRaceUnlocked((uint32_t)c->a)) return 0;
        c->status = 1;
        c->revision = g_state.revision;
        return 1;

    case CAMPAIGN_OP_FINISH_EVENT_RACE_METRICS:
        {
            CampaignRaceMetrics* metrics;
            int finish_status;

            metrics = (CampaignRaceMetrics*)(uintptr_t)(uint32_t)c->a;
            if (!metrics) return 0;

            CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
            finish_status = FinishEventRaceMetricsUnlocked(metrics);

            if (finish_status == 2) {
                c->out0 = 0;
                c->out1 = 0;
                c->out2 = 0;
                c->status = 1;
                c->revision = g_state.revision;
                return 1;
            }

            if (finish_status != 1) {
                CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
                return 0;
            }

            result = CommitMutationUnlocked();
            if (!result) {
                CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
                metrics->stars_awarded = 0;
                metrics->achieved_mask = 0;
                metrics->credits_awarded = 0;
                metrics->premium_awarded = 0;
                metrics->completion_count = 0;
                MoveFileExW(
                    g_race_session_consuming_path,
                    g_race_session_path,
                    MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
                );
                return 0;
            }

            DeleteFileW(g_race_session_consuming_path);

            c->out0 = metrics->credits_awarded;
            c->out1 = metrics->premium_awarded;
            c->out2 = metrics->stars_awarded;
        }
        break;

    case CAMPAIGN_OP_PURCHASE_OFFER:
        {
            const CampaignStoreOffer* offer = CampaignStoreCatalogFind(c->a);
            if (!offer) return 0;

            CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
            c->out0 = offer->item_id;

            if (!PurchaseStoreOfferUnlocked(offer, &c->out1, &c->out2)) {
                CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
                return 0;
            }

            result = CommitMutationUnlocked();
        }
        break;

    case CAMPAIGN_OP_SAVE:
        result = SaveStateUnlocked();
        break;

    case CAMPAIGN_OP_RELOAD:
        InterlockedExchange(&g_loaded, 0);
        EnsureLoadedUnlocked();
        result = 1;
        break;

    default:
        return 0;
    }

    if (!result) {
        CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
        c->status = 0;
        c->revision = g_state.revision;
        return 0;
    }

    c->status = 1;
    c->revision = g_state.revision;
    return 1;
}

int __cdecl CampaignExecuteCommand(CampaignCommand* command) {
    int result;

    if (!command || command->size < (uint32_t)sizeof(CampaignCommand)) return 0;

    LockState();
    EnsureLoadedUnlocked();
    result = ExecuteUnlocked(command);
    UnlockState();

    return result;
}
