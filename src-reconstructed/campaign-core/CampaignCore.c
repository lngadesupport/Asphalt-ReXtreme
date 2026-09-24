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
#include "CampaignPresentation.h"
#include "CampaignPhotoBindings.h"
#include "CampaignReplayBindings.h"
#include "CampaignOriginalUiBindings.h"
#include "CampaignRaceHudLayout.h"
#include "CampaignChallengeCatalog.h"

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

/* Verified x86 client adapter RVAs, relative to AMS.exe image base. */
#define CAMPAIGN_AMS_RVA_CURRENT_RACE_MANAGER 0x0153AC20u
#define CAMPAIGN_AMS_RVA_RESOLVE_CURRENT_RACE 0x00A42100u
#define CAMPAIGN_AMS_RVA_XOR_KEY_U32          0x0153A1C8u
#define CAMPAIGN_AMS_RVA_XOR_KEY_FLOAT        0x0153CC3Cu

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
static WCHAR g_config_path[1024];
static WCHAR g_legacy_campaign_dir[1024];
static WCHAR g_legacy_state_path[1024];
static WCHAR g_legacy_backup_path[1024];
static WCHAR g_executable_dir[1024];
static WCHAR g_user_dir[1024];
static volatile LONG g_portable_save;
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

static int EnsureDirectory(const WCHAR* path) {
    DWORD attrs;
    if (!path || !path[0]) return 0;
    attrs = GetFileAttributesW(path);
    if (attrs != INVALID_FILE_ATTRIBUTES) {
        return (attrs & FILE_ATTRIBUTE_DIRECTORY) ? 1 : 0;
    }
    if (CreateDirectoryW(path, 0)) return 1;
    return GetLastError() == ERROR_ALREADY_EXISTS ? 1 : 0;
}

static int BuildExecutableDirectory(WCHAR* out, uint32_t cap) {
    DWORD n;
    int i;

    if (!out || cap < 8) return 0;
    ZeroBytes(out, cap * (uint32_t)sizeof(WCHAR));
    n = GetModuleFileNameW(0, out, cap);
    if (n == 0 || n >= cap) return 0;

    i = (int)n - 1;
    while (i >= 0 && out[i] != L'\\' && out[i] != L'/') --i;
    if (i < 0) return 0;
    out[i + 1] = 0;
    return 1;
}

static int BuildLegacyPackagePaths(void) {
    WCHAR local[512];
    DWORD n;

    ZeroBytes(local, (uint32_t)sizeof(local));
    ZeroBytes(g_legacy_campaign_dir, (uint32_t)sizeof(g_legacy_campaign_dir));
    ZeroBytes(g_legacy_state_path, (uint32_t)sizeof(g_legacy_state_path));
    ZeroBytes(g_legacy_backup_path, (uint32_t)sizeof(g_legacy_backup_path));

    n = GetEnvironmentVariableW(L"LOCALAPPDATA", local, 512);
    if (n == 0 || n >= 512) return 0;

    if (!WideAppend(g_legacy_campaign_dir, 1024, local)) return 0;
    if (!WideAppend(
            g_legacy_campaign_dir,
            1024,
            L"\\Packages\\A278AB0D.AsphaltXtreme_h6adky7gbf63m\\LocalState\\CampaignEdition")) {
        return 0;
    }

    if (!WideAppend(g_legacy_state_path, 1024, g_legacy_campaign_dir)) return 0;
    if (!WideAppend(g_legacy_state_path, 1024, L"\\CampaignSave.dat")) return 0;

    if (!WideAppend(g_legacy_backup_path, 1024, g_legacy_campaign_dir)) return 0;
    if (!WideAppend(g_legacy_backup_path, 1024, L"\\CampaignSave.bak")) return 0;
    return 1;
}

static int ImportLegacyPackageSaveIfNeeded(void) {
    if (!g_portable_save) return 1;
    if (!g_legacy_state_path[0]) return 1;
    if (GetFileAttributesW(g_state_path) != INVALID_FILE_ATTRIBUTES) return 1;
    if (GetFileAttributesW(g_legacy_state_path) == INVALID_FILE_ATTRIBUTES) return 1;

    if (!CopyFileW(g_legacy_state_path, g_state_path, TRUE)) return 0;

    if (GetFileAttributesW(g_legacy_backup_path) != INVALID_FILE_ATTRIBUTES &&
        GetFileAttributesW(g_backup_path) == INVALID_FILE_ATTRIBUTES) {
        CopyFileW(g_legacy_backup_path, g_backup_path, TRUE);
    }
    return 1;
}

static int BuildPaths(void) {
    int portable_requested = 1;

    ZeroBytes(g_executable_dir, (uint32_t)sizeof(g_executable_dir));
    ZeroBytes(g_user_dir, (uint32_t)sizeof(g_user_dir));
    ZeroBytes(g_campaign_dir, (uint32_t)sizeof(g_campaign_dir));
    ZeroBytes(g_state_path, (uint32_t)sizeof(g_state_path));
    ZeroBytes(g_tmp_path, (uint32_t)sizeof(g_tmp_path));
    ZeroBytes(g_backup_path, (uint32_t)sizeof(g_backup_path));
    ZeroBytes(g_race_session_path, (uint32_t)sizeof(g_race_session_path));
    ZeroBytes(g_race_session_tmp_path, (uint32_t)sizeof(g_race_session_tmp_path));
    ZeroBytes(g_race_session_consuming_path, (uint32_t)sizeof(g_race_session_consuming_path));
    ZeroBytes(g_config_path, (uint32_t)sizeof(g_config_path));

    if (!BuildExecutableDirectory(g_executable_dir, 1024)) return 0;

    if (!WideAppend(g_config_path, 1024, g_executable_dir)) return 0;
    if (!WideAppend(g_config_path, 1024, L"ReXtreme.ini")) return 0;
    portable_requested = GetPrivateProfileIntW(L"Save", L"PortableSave", 1, g_config_path) ? 1 : 0;

    BuildLegacyPackagePaths();

    if (portable_requested) {
        if (!WideAppend(g_user_dir, 1024, g_executable_dir)) return 0;
        if (!WideAppend(g_user_dir, 1024, L"UserData")) return 0;

        if (EnsureDirectory(g_user_dir)) {
            if (!WideAppend(g_campaign_dir, 1024, g_user_dir)) return 0;
            if (!WideAppend(g_campaign_dir, 1024, L"\\CampaignEdition")) return 0;
            if (EnsureDirectory(g_campaign_dir)) {
                InterlockedExchange(&g_portable_save, 1);
            } else {
                ZeroBytes(g_campaign_dir, (uint32_t)sizeof(g_campaign_dir));
            }
        }
    }

    if (!g_campaign_dir[0]) {
        if (!g_legacy_campaign_dir[0]) return 0;
        if (!WideAppend(g_campaign_dir, 1024, g_legacy_campaign_dir)) return 0;
        if (!EnsureDirectory(g_campaign_dir)) return 0;
        InterlockedExchange(&g_portable_save, 0);
    }

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

    if (!ImportLegacyPackageSaveIfNeeded()) return 0;
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
        CampaignRaceSession* active = &g_race_session_buffer;

        if (!ReadRaceSessionFile(g_race_session_path, active)) return 0;
        if (active->event_id != event_id || active->car_id != car_id) return 0;

        if (session_id) *session_id = active->session_id;
        return 1;
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

static int CampaignReplayEnabledUnlocked(void) {
    CampaignPresentationSettings settings;
    ZeroBytes(&settings, (uint32_t)sizeof(settings));
    settings.size = (uint32_t)sizeof(settings);
    if (!CampaignPresentationGetSettings(&settings)) return 0;
    return (settings.flags & CAMPAIGN_PRESENTATION_REPLAY_ENABLED) ? 1 : 0;
}

static void CampaignReplayBeginLifecycleUnlocked(
    int32_t event_id,
    int32_t car_id,
    uint32_t session_id
) {
    CampaignReplayMetadata metadata;
    CampaignReplayMetadata current_metadata;
    CampaignPresentationDiagnostics diagnostics;
    CampaignReplayMarker marker;

    if (!CampaignReplayEnabledUnlocked()) return;

    /*
      GameModeGUIBase construction can re-enter for the same active race.
      Preserve an already-recording buffer when it belongs to the same
      Campaign race session.
    */
    ZeroBytes(&diagnostics, (uint32_t)sizeof(diagnostics));
    diagnostics.size = (uint32_t)sizeof(diagnostics);
    ZeroBytes(&current_metadata, (uint32_t)sizeof(current_metadata));
    current_metadata.size = (uint32_t)sizeof(current_metadata);

    if (CampaignPresentationGetDiagnostics(&diagnostics) &&
        diagnostics.replay_recording &&
        CampaignReplayGetMetadata(&current_metadata) &&
        current_metadata.session_id == session_id) {
        return;
    }

    /*
      Capacity is deliberately generous but bounded by CampaignReplayStart().
      At 30 samples/s, 32768 samples covers ~18 minutes of one-entity capture.
      The future verified sampling adapter may choose a different density.
    */
    if (!CampaignReplayStart(32768u)) return;

    ZeroBytes(&metadata, (uint32_t)sizeof(metadata));
    metadata.size = (uint32_t)sizeof(metadata);
    metadata.version = CAMPAIGN_REPLAY_FORMAT_VERSION;
    metadata.event_id = event_id;
    metadata.track_id = 0;      /* not mapped yet */
    metadata.player_car_id = car_id > 0 ? car_id : 0;
    metadata.race_mode = 0;     /* not mapped yet */
    metadata.session_id = session_id;
    CampaignReplaySetMetadata(&metadata);

    ZeroBytes(&marker, (uint32_t)sizeof(marker));
    marker.time_ms = 0;
    marker.type = CAMPAIGN_REPLAY_MARKER_START;
    marker.entity_id = car_id;
    marker.value = event_id;
    CampaignReplayAddMarker(&marker);
}

static void CampaignReplayFinishLifecycleUnlocked(
    const CampaignRaceMetrics* metrics
) {
    CampaignReplayMarker marker;

    if (!metrics) {
        CampaignReplayStop();
        return;
    }

    ZeroBytes(&marker, (uint32_t)sizeof(marker));
    marker.time_ms = metrics->finish_time_ms > 0 ?
        (uint32_t)metrics->finish_time_ms : 0u;
    marker.type = CAMPAIGN_REPLAY_MARKER_FINISH;
    marker.entity_id = 0;
    marker.value = metrics->placement;
    CampaignReplayAddMarker(&marker);
    CampaignReplayStop();

    /*
      Autosave succeeds only after the verified per-frame sampler has recorded
      at least one transform sample. Metadata-only sessions are intentionally
      not written as playable replay files.
    */
    CampaignReplaySaveAuto();
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

    if (position <= 0 || stars < 0 || finish_time_ms < 0) return 0;

    RecoverConsumingRaceSessionUnlocked();

    if (!ReadRaceSessionFile(g_race_session_path, session)) {
        if (session_id != 0 && session_id == g_state.last_completed_race_session_id) {
            if (credits_awarded) *credits_awarded = 0;
            if (premium_awarded) *premium_awarded = 0;
            if (completion_count) *completion_count = 0;
            return 2;
        }
        return 0;
    }

    if (session_id == 0) session_id = session->session_id;
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
    if (g_loaded) {
        /*
          Must run before any new Campaign mutation. A pending Challenge claim
          uses the Campaign revision to decide whether its reward was committed.
        */
        CampaignChallengesRecoverClaim(g_state.revision);
        return;
    }

    InitDefaultState(&g_state);
    if (!BuildPaths()) {
        InterlockedExchange(&g_loaded, 1);
        CampaignChallengesRecoverClaim(g_state.revision);
        return;
    }

    if (TryLoadV3(g_state_path, &g_state)) {
        InterlockedExchange(&g_loaded, 1);
        CampaignChallengesRecoverClaim(g_state.revision);
        return;
    }

    if (TryLoadV3(g_backup_path, &g_state)) {
        SaveStateUnlocked();
        InterlockedExchange(&g_loaded, 1);
        CampaignChallengesRecoverClaim(g_state.revision);
        return;
    }

    if (TryMigrateV2()) {
        InterlockedExchange(&g_loaded, 1);
        CampaignChallengesRecoverClaim(g_state.revision);
        return;
    }

    if (TryMigrateV1()) {
        InterlockedExchange(&g_loaded, 1);
        CampaignChallengesRecoverClaim(g_state.revision);
        return;
    }

    InitDefaultState(&g_state);
    SaveStateUnlocked();
    InterlockedExchange(&g_loaded, 1);
    CampaignChallengesRecoverClaim(g_state.revision);
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

static void* CampaignCallVirtual0(void* object, uint32_t slot_offset) {
    void* result = 0;

    if (!object) return 0;

    __asm {
        mov ecx, object
        mov eax, [ecx]
        mov edx, slot_offset
        call dword ptr [eax+edx]
        mov result, eax
    }
    return result;
}

static void* CampaignCallVirtual1(void* object, uint32_t slot_offset, void* arg0) {
    void* result = 0;

    if (!object) return 0;

    __asm {
        mov ecx, object
        mov eax, [ecx]
        mov edx, slot_offset
        push arg0
        call dword ptr [eax+edx]
        mov result, eax
    }
    return result;
}

static void* CampaignCallAmsThis0(void* function_address, void* object) {
    void* result = 0;

    if (!function_address || !object) return 0;

    __asm {
        mov ecx, object
        mov eax, function_address
        call eax
        mov result, eax
    }
    return result;
}

static uint32_t CampaignDecodeU32(void* address, uint32_t key) {
    uint32_t encoded;
    if (!address) return 0;
    encoded = *(volatile uint32_t*)address;
    return encoded ^ (uint32_t)(uintptr_t)address ^ key;
}

static int32_t CampaignRoundPositiveFloatBits(uint32_t bits) {
    uint32_t exponent;
    uint32_t mantissa;
    int32_t e;
    uint32_t shift;
    uint32_t integer_part;
    uint32_t remainder;
    uint32_t half;

    /* Negative, zero, subnormal, infinity and NaN are not valid distances. */
    if (bits & 0x80000000u) return 0;

    exponent = (bits >> 23) & 0xFFu;
    if (exponent == 0u || exponent == 0xFFu) return 0;

    e = (int32_t)exponent - 127;
    mantissa = (bits & 0x007FFFFFu) | 0x00800000u;

    if (e < -1) return 0;
    if (e == -1) return 1;

    if (e >= 31) return 0x7FFFFFFF;

    if (e >= 23) {
        uint32_t left = (uint32_t)(e - 23);
        if (left >= 8u || mantissa > (0x7FFFFFFFu >> left)) {
            return 0x7FFFFFFF;
        }
        return (int32_t)(mantissa << left);
    }

    shift = (uint32_t)(23 - e);
    integer_part = mantissa >> shift;
    remainder = mantissa & ((1u << shift) - 1u);
    half = 1u << (shift - 1u);

    if (remainder >= half && integer_part < 0x7FFFFFFFu) {
        ++integer_part;
    }

    return (int32_t)integer_part;
}

static void* CampaignResolveGameModeFromGui(void* game_mode_gui) {
    if (!game_mode_gui) return 0;
    return *(void**)((unsigned char*)game_mode_gui + 0x14);
}

static int32_t CampaignResolveEventIdFromGameMode(void* game_mode) {
    void* event_source;
    void* id_holder;

    if (!game_mode) return 0;

    /* Verified equivalent of 0x00CBFC20 after GameModeBase vfunc +0x24. */
    event_source = CampaignCallVirtual0(game_mode, 0x24);
    if (!event_source) return 0;

    id_holder = *(void**)((unsigned char*)event_source + 0xC0);
    if (!id_holder) return 0;

    return *(volatile int32_t*)id_holder;
}

static void* CampaignResolveRaceStats(void* game_mode) {
    void* player_token;
    void* entry;
    void* root;

    if (!game_mode) return 0;

    /*
      Verified read-only path from 0x00F0D880:
        token = GameModeBase::vfunc(+0x70)
        entry = GameModeBase::vfunc(+0xCC, token)
        root  = entry->+0x08
        stats = root+0xBC
    */
    player_token = CampaignCallVirtual0(game_mode, 0x70);
    if (!player_token) return 0;

    entry = CampaignCallVirtual1(game_mode, 0xCC, player_token);
    if (!entry) return 0;

    root = *(void**)((unsigned char*)entry + 0x08);
    if (!root) return 0;

    return (unsigned char*)root + 0xBC;
}

static int32_t CampaignResolvePlacement(void* ams_base) {
    void* manager;
    void* race_container;
    void* result_source;
    void* player;
    void* result;

    if (!ams_base) return 0;

    manager = *(void**)((unsigned char*)ams_base + CAMPAIGN_AMS_RVA_CURRENT_RACE_MANAGER);
    if (!manager) return 0;

    race_container = CampaignCallAmsThis0(
        (unsigned char*)ams_base + CAMPAIGN_AMS_RVA_RESOLVE_CURRENT_RACE,
        manager
    );
    if (!race_container) return 0;

    result_source = CampaignCallVirtual0(race_container, 0x40);
    if (!result_source) return 0;

    player = CampaignCallVirtual0(result_source, 0x70);
    if (!player) return 0;

    result = CampaignCallVirtual1(result_source, 0x40, player);
    return (int32_t)(uintptr_t)result;
}

static int32_t CampaignResolveFinishTimeMs(
    void* game_mode,
    uint32_t xor_key
) {
    void* address;
    uint32_t value;
    void* fallback_entry;
    int32_t fallback_token;

    if (!game_mode) return 0;

    address = (unsigned char*)game_mode + 0x98;
    value = CampaignDecodeU32(address, xor_key);
    if ((int32_t)value > 0) return (int32_t)value;

    /*
      Verified fallback from 0x00F0D880:
        entry = GameModeBase::vfunc(+0xCC, *(game_mode+0x8C))
        timer = decode(entry+0x3C)
    */
    fallback_token = *(volatile int32_t*)((unsigned char*)game_mode + 0x8C);
    fallback_entry = CampaignCallVirtual1(
        game_mode,
        0xCC,
        (void*)(uintptr_t)(uint32_t)fallback_token
    );
    if (!fallback_entry) return 0;

    value = CampaignDecodeU32(
        (unsigned char*)fallback_entry + 0x3C,
        xor_key
    );
    return (int32_t)value;
}

static int CampaignExtractRaceMetrics(
    void* game_mode_gui,
    CampaignRaceMetrics* metrics
) {
    void* ams_base;
    void* game_mode;
    void* stats;
    uint32_t key_u32;
    uint32_t key_float;
    uint32_t drift_bits;

    if (!game_mode_gui || !metrics) return 0;

    ZeroBytes(metrics, (uint32_t)sizeof(*metrics));
    metrics->size = (uint32_t)sizeof(*metrics);
    metrics->version = CAMPAIGN_RACE_METRICS_VERSION;

    ams_base = (void*)GetModuleHandleW(0);
    if (!ams_base) return 0;

    game_mode = CampaignResolveGameModeFromGui(game_mode_gui);
    if (!game_mode) return 0;

    key_u32 = *(volatile uint32_t*)(
        (unsigned char*)ams_base + CAMPAIGN_AMS_RVA_XOR_KEY_U32
    );
    key_float = *(volatile uint32_t*)(
        (unsigned char*)ams_base + CAMPAIGN_AMS_RVA_XOR_KEY_FLOAT
    );

    metrics->placement = CampaignResolvePlacement(ams_base);
    metrics->finish_time_ms = CampaignResolveFinishTimeMs(game_mode, key_u32);

    stats = CampaignResolveRaceStats(game_mode);
    if (!stats) return 0;

    /*
      Verified source offsets behind the 0x00F0D880 telemetry producer.
      They are read-only engine counters. Campaign logic does not call the
      old serializer and does not trust its reward/star decisions.
    */
    drift_bits = CampaignDecodeU32((unsigned char*)stats + 0x64, key_float);
    metrics->drift_meters = CampaignRoundPositiveFloatBits(drift_bits);

    metrics->air_time_ms = (int32_t)CampaignDecodeU32(
        (unsigned char*)stats + 0x70, key_u32
    );
    metrics->nitro_time_ms = (int32_t)CampaignDecodeU32(
        (unsigned char*)stats + 0x90, key_u32
    );
    metrics->obstacles_broken = (int32_t)CampaignDecodeU32(
        (unsigned char*)stats + 0x30, key_u32
    );
    metrics->flat_spins = (int32_t)CampaignDecodeU32(
        (unsigned char*)stats + 0x50, key_u32
    );
    metrics->barrel_rolls = (int32_t)CampaignDecodeU32(
        (unsigned char*)stats + 0xB4, key_u32
    );
    metrics->nitro_all_in = (int32_t)CampaignDecodeU32(
        (unsigned char*)stats + 0x88, key_u32
    );
    metrics->nitro_chain = (int32_t)CampaignDecodeU32(
        (unsigned char*)stats + 0x84, key_u32
    );
    metrics->nitro_normal = (int32_t)CampaignDecodeU32(
        (unsigned char*)stats + 0xB8, key_u32
    );
    metrics->wrecked_cars = (int32_t)CampaignDecodeU32(
        (unsigned char*)stats + 0xC0, key_u32
    );
    metrics->wrecked_environment = (int32_t)CampaignDecodeU32(
        (unsigned char*)stats + 0xC4, key_u32
    );
    metrics->wrecks_made = (int32_t)CampaignDecodeU32(
        (unsigned char*)stats + 0x00, key_u32
    );

    if (metrics->placement <= 0 || metrics->placement > 7) return 0;
    if (metrics->finish_time_ms < 0) return 0;

    return 1;
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

int __cdecl CampaignBeginRaceFromGui(void* game_mode_gui) {
    void* game_mode;
    int32_t event_id;
    uint32_t session_id = 0;
    int result = 0;

    game_mode = CampaignResolveGameModeFromGui(game_mode_gui);
    event_id = CampaignResolveEventIdFromGameMode(game_mode);
    if (event_id <= 0) return 0;

    LockState();
    EnsureLoadedUnlocked();

    RecoverConsumingRaceSessionUnlocked();

    /*
      Constructor re-entry for the same still-active event is idempotent.
      A different active event is treated as an abandoned previous race.
    */
    if (ReadRaceSessionFile(g_race_session_path, &g_race_session_buffer)) {
        if (g_race_session_buffer.event_id == event_id) {
            session_id = g_race_session_buffer.session_id;
            result = 1;
        } else {
            DeleteFileW(g_race_session_path);
        }
    }

    if (!result) {
        result = BeginEventRaceUnlocked(event_id, 0, &session_id);
    }

    if (result) {
        CampaignReplayBeginLifecycleUnlocked(event_id, 0, session_id);
    }

    UnlockState();
    return result ? (int)session_id : 0;
}

int __cdecl CampaignReplayFrameFromGui(void* game_mode_gui) {
    CampaignPresentationDiagnostics diagnostics;
    CampaignReplaySample sample;
    int handled = 0;

    if (!game_mode_gui) return 0;

    /*
      The verified per-frame GameModeGUIBase hook is also the natural place to
      keep a saved layout applied to the live original HUD instance. The layout
      adapter itself remains fail-closed on UI + field bindings.
    */
    if (CampaignRaceHudLayoutCount() > 0 &&
        CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_RACE_HUD) &&
        CampaignRaceHudLayoutApplyFromGui(game_mode_gui)) {
        handled = 1;
    }

    ZeroBytes(&diagnostics, (uint32_t)sizeof(diagnostics));
    diagnostics.size = (uint32_t)sizeof(diagnostics);
    if (!CampaignPresentationGetDiagnostics(&diagnostics)) return handled;
    if (!diagnostics.replay_recording) return handled;

    /*
      Fail closed until the exact player transform chain for 1.7.3.8 is
      represented by CampaignReplayBindings.dat. No offsets are hardcoded here.
    */
    if (!CampaignReplayBindingsReady()) return handled;

    ZeroBytes(&sample, (uint32_t)sizeof(sample));
    if (!CampaignReplayBindingsSample(game_mode_gui, &sample)) return handled;
    if (CampaignReplayRecordFrame(&sample)) handled = 1;
    return handled;
}

int __cdecl CampaignPhotoFrameFromGui(void* game_mode_gui) {
    CampaignPresentationSettings settings;
    CampaignPhotoState photo;

    if (!game_mode_gui) return 0;

    ZeroBytes(&settings, (uint32_t)sizeof(settings));
    settings.size = (uint32_t)sizeof(settings);
    if (!CampaignPresentationGetSettings(&settings)) return 0;
    if (!(settings.flags & CAMPAIGN_PRESENTATION_PHOTO_ENABLED)) return 0;

    ZeroBytes(&photo, (uint32_t)sizeof(photo));
    photo.size = (uint32_t)sizeof(photo);
    if (!CampaignPhotoGet(&photo) || !photo.active) return 0;

    /*
      This call is fail-closed: CampaignPhotoBindingsApply requires the full
      verified semantic set for Free Camera and writable proven targets.
    */
    return CampaignPhotoBindingsApply(&photo);
}

int __cdecl CampaignPhotoToggleFromGui(void* game_mode_gui) {
    CampaignPresentationSettings settings;
    CampaignPhotoState photo;

    if (!game_mode_gui) return 0;

    ZeroBytes(&settings, (uint32_t)sizeof(settings));
    settings.size = (uint32_t)sizeof(settings);
    if (!CampaignPresentationGetSettings(&settings) ||
        !(settings.flags & CAMPAIGN_PRESENTATION_PHOTO_ENABLED)) {
        return 0;
    }

    /*
      ReXtreme does not expose a substitute Photo UI. The pause hook may only
      open Photo Mode after the complete original Asphalt UI set is verified.
    */
    if (!CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_PHOTO_MODE)) {
        return 0;
    }

    ZeroBytes(&photo, (uint32_t)sizeof(photo));
    photo.size = (uint32_t)sizeof(photo);
    if (!CampaignPhotoGet(&photo)) return 0;

    if (photo.active) return CampaignPhotoExit();

    if (!CampaignPhotoBindingsReady(CAMPAIGN_PHOTO_CAMERA_FREE)) return 0;
    return CampaignPhotoEnter(0);
}

int __cdecl CampaignFinishRaceFromGui(void* game_mode_gui) {
    CampaignRaceMetrics metrics;
    int finish_status;
    int result = 0;

    LockState();
    EnsureLoadedUnlocked();

    RecoverConsumingRaceSessionUnlocked();

    if (!ReadRaceSessionFile(g_race_session_path, &g_race_session_buffer)) {
        UnlockState();
        return 0;
    }

    if (!CampaignExtractRaceMetrics(game_mode_gui, &metrics)) {
        CampaignReplayStop();
        UnlockState();
        return 0;
    }

    metrics.session_id = g_race_session_buffer.session_id;
    CampaignReplayFinishLifecycleUnlocked(&metrics);

    CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
    finish_status = FinishEventRaceMetricsUnlocked(&metrics);

    if (finish_status == 2) {
        UnlockState();
        return 1;
    }

    if (finish_status == 1) {
        result = CommitMutationUnlocked();
        if (result) {
            DeleteFileW(g_race_session_consuming_path);
            /* Challenge sidecar is secondary: a failure never invalidates the race commit. */
            CampaignChallengesOnRace(g_race_session_buffer.event_id, &metrics);
        } else {
            CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
            MoveFileExW(
                g_race_session_consuming_path,
                g_race_session_path,
                MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
            );
        }
    } else {
        CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
    }

    UnlockState();
    return result;
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
            /* Only full metric finishes contribute to Challenges. */
            CampaignChallengesOnRace(g_race_session_buffer.event_id, metrics);

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

    case CAMPAIGN_OP_DIAGNOSTICS:
        c->out0 = InterlockedCompareExchange(&g_portable_save, 0, 0) ? 1 : 0;
        c->out1 = (int32_t)CAMPAIGN_VERSION;
        c->out2 =
            GetFileAttributesW(g_race_session_path) != INVALID_FILE_ATTRIBUTES ? 1 : 0;
        c->status = 1;
        c->revision = g_state.revision;
        return 1;

    case CAMPAIGN_OP_CHALLENGE_COUNT:
        c->out0 = (int32_t)CampaignChallengeCatalogCount();
        c->status = 1;
        c->revision = g_state.revision;
        return 1;

    case CAMPAIGN_OP_CHALLENGE_ID_AT:
        {
            const CampaignChallengeDefinition* def =
                CampaignChallengeCatalogGet((uint32_t)c->a);
            if (!def) return 0;
            c->out0 = def->challenge_id;
            c->status = 1;
            c->revision = g_state.revision;
            return 1;
        }

    case CAMPAIGN_OP_CHALLENGE_STATUS:
        {
            CampaignChallengeStatus status;
            ZeroBytes(&status, (uint32_t)sizeof(status));
            status.size = (uint32_t)sizeof(status);
            if (!CampaignChallengesGetStatus(c->a, &status)) return 0;
            c->out0 = status.progress;
            c->out1 = status.goal;
            c->out2 =
                (status.completed ? 1 : 0) |
                (status.claimed ? 2 : 0) |
                (status.has_progress ? 4 : 0) |
                ((status.scope & 0xFF) << 8) |
                ((status.metric & 0xFF) << 16) |
                ((status.progress_mode & 0xFF) << 24);
            c->status = 1;
            c->revision = g_state.revision;
            return 1;
        }

    case CAMPAIGN_OP_CHALLENGE_REWARD:
        {
            CampaignChallengeStatus status;
            ZeroBytes(&status, (uint32_t)sizeof(status));
            status.size = (uint32_t)sizeof(status);
            if (!CampaignChallengesGetStatus(c->a, &status)) return 0;
            c->out0 = status.reward_credits;
            c->out1 = status.reward_premium;
            c->out2 = status.reward_item_id;
            c->status = 1;
            c->revision = g_state.revision;
            return 1;
        }

    case CAMPAIGN_OP_CHALLENGE_ITEM_REWARD:
        {
            CampaignChallengeStatus status;
            ZeroBytes(&status, (uint32_t)sizeof(status));
            status.size = (uint32_t)sizeof(status);
            if (!CampaignChallengesGetStatus(c->a, &status)) return 0;
            c->out0 = status.reward_item_id;
            c->out1 = status.reward_item_amount;
            c->out2 = status.completed && !status.claimed ? 1 : 0;
            c->status = 1;
            c->revision = g_state.revision;
            return 1;
        }

    case CAMPAIGN_OP_CHALLENGE_REFRESH:
        c->out0 = CampaignChallengesRefreshPeriods() ? 1 : 0;
        c->status = 1;
        c->revision = g_state.revision;
        return 1;

    case CAMPAIGN_OP_CHALLENGE_CLAIM:
        {
            CampaignChallengeStatus status;
            CampaignChallengeClaim claim;
            int has_reward;

            ZeroBytes(&status, (uint32_t)sizeof(status));
            status.size = (uint32_t)sizeof(status);
            if (!CampaignChallengesGetStatus(c->a, &status)) return 0;

            c->out0 = status.reward_credits;
            c->out1 = status.reward_premium;
            c->out2 = status.reward_item_id;

            /* Idempotent UI retry after a completed claim. */
            if (status.claimed) {
                c->status = 1;
                c->revision = g_state.revision;
                return 1;
            }
            if (!status.completed) return 0;

            ZeroBytes(&claim, (uint32_t)sizeof(claim));
            claim.size = (uint32_t)sizeof(claim);
            if (!CampaignChallengesBeginClaim(c->a, g_state.revision, &claim)) return 0;

            /*
              If a prior reward commit is already visible by revision, finalize
              the journal only. Never grant it a second time.
            */
            if (g_state.revision > claim.start_campaign_revision) {
                if (!CampaignChallengesFinalizeClaim(c->a, g_state.revision)) return 0;
                c->status = 1;
                c->revision = g_state.revision;
                return 1;
            }

            has_reward =
                claim.reward_credits > 0 ||
                claim.reward_premium > 0 ||
                claim.reward_item_id > 0;

            if (!has_reward) {
                if (!CampaignChallengesFinalizeClaim(c->a, g_state.revision)) return 0;
                c->status = 1;
                c->revision = g_state.revision;
                return 1;
            }

            if (claim.reward_credits > 0 &&
                g_state.credits > 0x7FFFFFFF - claim.reward_credits) return 0;
            if (claim.reward_premium > 0 &&
                g_state.premium_currency > 0x7FFFFFFF - claim.reward_premium) return 0;

            CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));
            g_state.credits += claim.reward_credits;
            g_state.premium_currency += claim.reward_premium;

            if (claim.reward_item_id > 0 &&
                !InventoryAddNoSave(claim.reward_item_id, claim.reward_item_amount)) {
                CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
                return 0;
            }

            result = CommitMutationUnlocked();
            if (!result) {
                CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
                return 0;
            }

            /*
              Reward is durably committed now. If sidecar finalization fails,
              the pending journal remains; the next EnsureLoadedUnlocked()
              sees revision > start_revision and finalizes without regranting.
            */
            CampaignChallengesFinalizeClaim(c->a, g_state.revision);
            c->status = 1;
            c->revision = g_state.revision;
            return 1;
        }

    case CAMPAIGN_OP_GET_PROFILE_SUMMARY:
        switch (c->a) {
        case CAMPAIGN_PROFILE_SUMMARY_PROGRESS:
            c->out0 = (int32_t)g_state.race_count;
            c->out1 = (int32_t)g_state.total_stars;
            c->out2 = (int32_t)g_state.owned_count;
            break;
        case CAMPAIGN_PROFILE_SUMMARY_ECONOMY:
            c->out0 = g_state.credits;
            c->out1 = g_state.premium_currency;
            c->out2 = (int32_t)g_state.craft_count;
            break;
        case CAMPAIGN_PROFILE_SUMMARY_GARAGE:
            c->out0 = g_state.selected_car_id;
            c->out1 = g_state.last_acquired_car_id;
            c->out2 = (int32_t)g_state.event_state_count;
            break;
        default:
            return 0;
        }
        c->status = 1;
        c->revision = g_state.revision;
        return 1;

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

int __cdecl CampaignBeginRaceAdapter(const CampaignRaceBeginArgs* args) {
    uint32_t session_id = 0;
    int result;

    if (!args || args->event_id <= 0) return 0;

    LockState();
    EnsureLoadedUnlocked();
    result = BeginEventRaceUnlocked(args->event_id, args->car_id, &session_id);
    if (result) {
        CampaignReplayBeginLifecycleUnlocked(args->event_id, args->car_id, session_id);
    }
    UnlockState();

    return result;
}

int __cdecl CampaignFinishRaceAdapter(const CampaignRaceFinishArgs* args) {
    int result;
    int finish_status;

    if (!args || args->position <= 0 || args->stars < 0 || args->finish_time_ms < 0) return 0;

    LockState();
    EnsureLoadedUnlocked();

    CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));

    finish_status = FinishEventRaceUnlocked(
        0,
        args->position,
        args->stars,
        args->finish_time_ms,
        0,
        0,
        0
    );

    {
        CampaignRaceMetrics replay_metrics;
        ZeroBytes(&replay_metrics, (uint32_t)sizeof(replay_metrics));
        replay_metrics.size = (uint32_t)sizeof(replay_metrics);
        replay_metrics.version = CAMPAIGN_RACE_METRICS_VERSION;
        replay_metrics.placement = args->position;
        replay_metrics.finish_time_ms = args->finish_time_ms;
        CampaignReplayFinishLifecycleUnlocked(&replay_metrics);
    }

    if (finish_status == 2) {
        UnlockState();
        return 1;
    }

    if (finish_status != 1) {
        CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
        UnlockState();
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
        UnlockState();
        return 0;
    }

    DeleteFileW(g_race_session_consuming_path);
    UnlockState();
    return 1;
}

int __cdecl CampaignApplyUpgradeBatch(CampaignUpgradeBatchArgs* args) {
    uint32_t i;
    uint32_t j;
    int result;

    if (!args || args->size < (uint32_t)sizeof(CampaignUpgradeBatchArgs)) return 0;

    args->status = 0;
    args->applied_count = 0;
    args->revision = 0;

    if (args->car_id <= 0 ||
        args->count == 0 ||
        args->count > CAMPAIGN_UPGRADE_BATCH_MAX) {
        return 0;
    }

    /* One visual action id may appear only once in a transaction. */
    for (i = 0; i < args->count; ++i) {
        if (args->ui_action_ids[i] <= 0) return 0;
        for (j = 0; j < i; ++j) {
            if (args->ui_action_ids[i] == args->ui_action_ids[j]) return 0;
        }
    }

    LockState();
    EnsureLoadedUnlocked();

    CopyBytes(&g_tx_backup, &g_state, (uint32_t)sizeof(g_state));

    for (i = 0; i < args->count; ++i) {
        if (!ApplyUpgradeUiActionUnlocked(
                args->car_id,
                args->ui_action_ids[i],
                0,
                0,
                0)) {
            CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
            args->revision = g_state.revision;
            UnlockState();
            return 0;
        }
        ++args->applied_count;
    }

    result = CommitMutationUnlocked();
    if (!result) {
        CopyBytes(&g_state, &g_tx_backup, (uint32_t)sizeof(g_state));
        args->applied_count = 0;
        args->revision = g_state.revision;
        UnlockState();
        return 0;
    }

    args->status = 1;
    args->revision = g_state.revision;
    UnlockState();
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
