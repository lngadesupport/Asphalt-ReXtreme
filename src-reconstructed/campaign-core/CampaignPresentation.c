#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignPresentation.h"
#include "CampaignPresentationCatalog.h"
#include "CampaignPresentationBindings.h"
#include "CampaignPhotoBindings.h"
#include "CampaignReplayBindings.h"
#include "CampaignOriginalUiBindings.h"
#include "CampaignRaceHudBindings.h"

#define RXPS_MAGIC 0x53505852u /* RXPS */
#define RXRP_MAGIC 0x50525852u /* RXRP */
#define RX_REPLAY_MIN_CAPACITY 256u
#define RX_REPLAY_MAX_CAPACITY 524288u
#define RX_REPLAY_FRAME_INTERVAL_MS 33u

typedef struct CampaignPresentationDisk {
    uint32_t magic;
    CampaignPresentationSettings settings;
} CampaignPresentationDisk;

typedef struct CampaignReplayFileHeader {
    uint32_t magic;
    uint32_t version;
    uint32_t sample_size;
    uint32_t sample_count;
    uint32_t marker_size;
    uint32_t marker_count;
    uint32_t first_time_ms;
    uint32_t last_time_ms;
    uint32_t sample_hash;
    uint32_t marker_hash;
    CampaignReplayMetadata metadata;
} CampaignReplayFileHeader;

static volatile LONG g_presentation_lock;
static CampaignPresentationSettings g_settings;
static volatile LONG g_settings_loaded;

static CampaignReplaySample* g_replay_samples;
static uint32_t g_replay_capacity;
static uint32_t g_replay_count;
static uint32_t g_replay_write;
static uint32_t g_replay_dropped;
static uint32_t g_replay_throttled;
static uint32_t g_replay_last_frame_time_ms;
static uint32_t g_replay_last_frame_valid;
static uint32_t g_replay_active;
static CampaignReplayMarker g_replay_markers[CAMPAIGN_REPLAY_MARKER_MAX];
static uint32_t g_replay_marker_count;
static uint32_t g_replay_dropped_markers;
static CampaignReplayPlaybackState g_playback;
static CampaignReplayMetadata g_replay_metadata;

static CampaignPhotoState g_photo;
static CampaignPhotoState g_photo_restore;
static uint32_t g_photo_restore_valid;

static WCHAR g_settings_path[1024];
static WCHAR g_settings_tmp[1024];
static WCHAR g_settings_bak[1024];
static WCHAR g_replay_auto_path[1024];
static WCHAR g_replay_auto_dir[1024];
static CampaignReplayLibraryEntry g_replay_library[CAMPAIGN_REPLAY_LIBRARY_MAX];
static uint32_t g_replay_library_count;
static WCHAR g_replay_library_pattern[1024];
static WCHAR g_replay_library_path[1024];

static void PresentationLock(void) {
    while (InterlockedCompareExchange(&g_presentation_lock, 1, 0) != 0) Sleep(0);
}

static void PresentationUnlock(void) {
    InterlockedExchange(&g_presentation_lock, 0);
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

static uint32_t HashUpdate(uint32_t h, const void* p, uint32_t count) {
    const unsigned char* s = (const unsigned char*)p;
    uint32_t i;
    for (i = 0; i < count; ++i) {
        h ^= s[i];
        h *= 16777619u;
    }
    return h;
}

static uint32_t HashBytes(const void* p, uint32_t count) {
    return HashUpdate(2166136261u, p, count);
}

static uint32_t SettingsChecksum(const CampaignPresentationSettings* settings) {
    CampaignPresentationSettings temp;
    CopyBytes(&temp, settings, (uint32_t)sizeof(temp));
    temp.checksum = 0;
    return HashBytes(&temp, (uint32_t)sizeof(temp));
}

static int WideCopy(WCHAR* dst, uint32_t cap, const WCHAR* src) {
    uint32_t i = 0;
    if (!dst || cap == 0 || !src) return 0;
    while (src[i]) {
        if (i + 1 >= cap) return 0;
        dst[i] = src[i];
        ++i;
    }
    dst[i] = 0;
    return 1;
}

static int WideAppend(WCHAR* dst, uint32_t cap, const WCHAR* src) {
    uint32_t n = 0;
    uint32_t i = 0;
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

static int EnsureDirectoryPath(const WCHAR* path) {
    DWORD attrs;
    if (!path || !path[0]) return 0;
    attrs = GetFileAttributesW(path);
    if (attrs != INVALID_FILE_ATTRIBUTES) {
        return (attrs & FILE_ATTRIBUTE_DIRECTORY) ? 1 : 0;
    }
    if (CreateDirectoryW(path, 0)) return 1;
    return GetLastError() == ERROR_ALREADY_EXISTS ? 1 : 0;
}

static int AppendHex8(WCHAR* dst, uint32_t cap, uint32_t value) {
    static const WCHAR digits[] = L"0123456789ABCDEF";
    WCHAR text[9];
    uint32_t i;
    for (i = 0; i < 8; ++i) {
        uint32_t shift = (7u - i) * 4u;
        text[i] = digits[(value >> shift) & 0xFu];
    }
    text[8] = 0;
    return WideAppend(dst, cap, text);
}

static int BuildReplayDirectoryUnlocked(void) {
    WCHAR exe[1024];
    DWORD n;
    int i;

    ZeroBytes(exe, (uint32_t)sizeof(exe));
    ZeroBytes(g_replay_auto_dir, (uint32_t)sizeof(g_replay_auto_dir));

    n = GetModuleFileNameW(0, exe, 1024);
    if (n == 0 || n >= 1024) return 0;

    i = (int)n - 1;
    while (i >= 0 && exe[i] != L'\\' && exe[i] != L'/') --i;
    if (i < 0) return 0;
    exe[i + 1] = 0;

    if (!WideCopy(g_replay_auto_dir, 1024, exe)) return 0;
    if (!WideAppend(g_replay_auto_dir, 1024, L"UserData")) return 0;
    if (!EnsureDirectoryPath(g_replay_auto_dir)) return 0;
    if (!WideAppend(g_replay_auto_dir, 1024, L"\\Replays")) return 0;
    if (!EnsureDirectoryPath(g_replay_auto_dir)) return 0;
    return 1;
}

static int BuildReplayAutoPathUnlocked(void) {
    ZeroBytes(g_replay_auto_path, (uint32_t)sizeof(g_replay_auto_path));
    if (!BuildReplayDirectoryUnlocked()) return 0;

    if (!WideCopy(g_replay_auto_path, 1024, g_replay_auto_dir)) return 0;
    if (!WideAppend(g_replay_auto_path, 1024, L"\\Replay-E")) return 0;
    if (!AppendHex8(
            g_replay_auto_path,
            1024,
            (uint32_t)g_replay_metadata.event_id)) return 0;
    if (!WideAppend(g_replay_auto_path, 1024, L"-S")) return 0;
    if (!AppendHex8(
            g_replay_auto_path,
            1024,
            g_replay_metadata.session_id)) return 0;
    if (!WideAppend(g_replay_auto_path, 1024, L".rexreplay")) return 0;
    return 1;
}

static int BuildSettingsPaths(void) {
    WCHAR exe[1024];
    DWORD n;
    int i;

    if (g_settings_path[0]) return 1;
    ZeroBytes(exe, (uint32_t)sizeof(exe));

    n = GetModuleFileNameW(0, exe, 1024);
    if (n == 0 || n >= 1024) return 0;

    i = (int)n - 1;
    while (i >= 0 && exe[i] != L'\\' && exe[i] != L'/') --i;
    if (i < 0) return 0;
    exe[i + 1] = 0;

    if (!WideCopy(g_settings_path, 1024, exe)) return 0;
    if (!WideAppend(g_settings_path, 1024, L"ReXtremePresentation.dat")) return 0;

    if (!WideCopy(g_settings_tmp, 1024, exe)) return 0;
    if (!WideAppend(g_settings_tmp, 1024, L"ReXtremePresentation.tmp")) return 0;

    if (!WideCopy(g_settings_bak, 1024, exe)) return 0;
    if (!WideAppend(g_settings_bak, 1024, L"ReXtremePresentation.bak")) return 0;
    return 1;
}

static void InitSettings(CampaignPresentationSettings* settings) {
    ZeroBytes(settings, (uint32_t)sizeof(*settings));
    settings->size = (uint32_t)sizeof(*settings);
    settings->version = CAMPAIGN_PRESENTATION_SETTINGS_VERSION;
    settings->revision = 1;
    settings->flags = CAMPAIGN_PRESENTATION_REPLAY_ENABLED | CAMPAIGN_PRESENTATION_PHOTO_ENABLED;

    /* Every override remains zero: original game behavior until proven/bound. */
    settings->checksum = SettingsChecksum(settings);
}

static int CapabilityAllowsValue(const char* id, int32_t value) {
    const CampaignPresentationCapability* capability;
    int32_t delta;

    /* Zero is always the explicit "use original game behavior" sentinel. */
    if (value == 0) return 1;

    capability = CampaignPresentationCatalogFind(id);
    if (!capability) return 0;
    if (!(capability->flags & CAMPAIGN_PRESENTATION_CAPABILITY_VERIFIED)) return 0;
    if (value < capability->minimum || value > capability->maximum) return 0;

    if (capability->step > 0) {
        delta = value - capability->minimum;
        if ((delta % capability->step) != 0) return 0;
    }
    return 1;
}

static int ApplyLegacyPresentationValue(const char* id, int32_t value) {
    const CampaignPresentationCapability* capability;

    capability = CampaignPresentationCatalogFind(id);

    if (value == 0) {
        /*
          No verified capability means "leave original Asphalt Xtreme behavior
          untouched". If a capability exists, resetting requires a real binding
          so the proven original value can be restored.
        */
        if (!capability) return 1;
        return CampaignPresentationBindingsApply(
            id,
            capability->original_value
        );
    }

    if (!capability) return 0;
    return CampaignPresentationBindingsApply(id, value);
}

static int ApplyLegacyPresentationBindings(
    const CampaignPresentationSettings* settings
) {
    if (!settings) return 0;
    if (!ApplyLegacyPresentationValue("fov", settings->fov_x100)) return 0;
    if (!ApplyLegacyPresentationValue(
            "camera_distance",
            settings->camera_distance_x1000)) return 0;
    if (!ApplyLegacyPresentationValue(
            "camera_height",
            settings->camera_height_x1000)) return 0;
    if (!ApplyLegacyPresentationValue(
            "camera_smoothing",
            settings->camera_smoothing_x1000)) return 0;
    return 1;
}

static int ValidateSettings(const CampaignPresentationSettings* settings) {
    if (!settings) return 0;
    if (settings->size != (uint32_t)sizeof(*settings)) return 0;
    if (settings->version != CAMPAIGN_PRESENTATION_SETTINGS_VERSION) return 0;

    /*
      This validates storage safety only. It intentionally does not claim a
      supported renderer range. Runtime adapters must clamp/apply only values
      confirmed by the capability audit for the original build.
    */
    if (settings->fov_x100 < 0) return 0;
    if (settings->camera_distance_x1000 < 0) return 0;
    if (settings->camera_height_x1000 < -1000000 || settings->camera_height_x1000 > 1000000) return 0;
    if (settings->camera_smoothing_x1000 < 0) return 0;

    if (!CapabilityAllowsValue("fov", settings->fov_x100)) return 0;
    if (!CapabilityAllowsValue("camera_distance", settings->camera_distance_x1000)) return 0;
    if (!CapabilityAllowsValue("camera_height", settings->camera_height_x1000)) return 0;
    if (!CapabilityAllowsValue("camera_smoothing", settings->camera_smoothing_x1000)) return 0;

    if (settings->checksum != SettingsChecksum(settings)) return 0;
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

static int LoadSettingsUnlocked(void) {
    HANDLE h;
    DWORD got = 0;
    CampaignPresentationDisk disk;

    if (!BuildSettingsPaths()) return 0;
    ZeroBytes(&disk, (uint32_t)sizeof(disk));

    h = CreateFileW(
        g_settings_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );
    if (h == INVALID_HANDLE_VALUE) {
        InitSettings(&g_settings);
        InterlockedExchange(&g_settings_loaded, 1);
        return 1;
    }

    if (!ReadFile(h, &disk, (DWORD)sizeof(disk), &got, 0) ||
        got != (DWORD)sizeof(disk) ||
        disk.magic != RXPS_MAGIC ||
        !ValidateSettings(&disk.settings)) {
        CloseHandle(h);
        InitSettings(&g_settings);
        InterlockedExchange(&g_settings_loaded, 1);
        return 1;
    }

    CloseHandle(h);
    CopyBytes(&g_settings, &disk.settings, (uint32_t)sizeof(g_settings));
    InterlockedExchange(&g_settings_loaded, 1);
    return 1;
}

static void EnsureSettingsUnlocked(void) {
    if (InterlockedCompareExchange(&g_settings_loaded, 1, 1) == 0) {
        LoadSettingsUnlocked();
    }
}

static int SaveSettingsUnlocked(void) {
    CampaignPresentationDisk disk;
    int had_current;

    if (!BuildSettingsPaths()) return 0;
    EnsureSettingsUnlocked();

    ++g_settings.revision;
    g_settings.checksum = SettingsChecksum(&g_settings);

    ZeroBytes(&disk, (uint32_t)sizeof(disk));
    disk.magic = RXPS_MAGIC;
    CopyBytes(&disk.settings, &g_settings, (uint32_t)sizeof(g_settings));

    DeleteFileW(g_settings_tmp);
    if (!WriteWholeFile(g_settings_tmp, &disk, (DWORD)sizeof(disk))) return 0;

    had_current = (GetFileAttributesW(g_settings_path) != INVALID_FILE_ATTRIBUTES);
    DeleteFileW(g_settings_bak);

    if (had_current) {
        if (!MoveFileExW(
                g_settings_path,
                g_settings_bak,
                MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
            DeleteFileW(g_settings_tmp);
            return 0;
        }
    }

    if (!MoveFileExW(
            g_settings_tmp,
            g_settings_path,
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        if (had_current) {
            MoveFileExW(
                g_settings_bak,
                g_settings_path,
                MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
            );
        }
        DeleteFileW(g_settings_tmp);
        return 0;
    }
    return 1;
}

int __cdecl CampaignPresentationLoadSettings(void) {
    int result;
    PresentationLock();
    result = LoadSettingsUnlocked();
    if (result) {
        result = ApplyLegacyPresentationBindings(&g_settings);
    }
    PresentationUnlock();
    return result;
}

int __cdecl CampaignPresentationSaveSettings(void) {
    int result;
    PresentationLock();
    result = SaveSettingsUnlocked();
    PresentationUnlock();
    return result;
}

int __cdecl CampaignPresentationGetSettings(CampaignPresentationSettings* out) {
    if (!out || out->size < (uint32_t)sizeof(*out)) return 0;
    PresentationLock();
    EnsureSettingsUnlocked();
    CopyBytes(out, &g_settings, (uint32_t)sizeof(g_settings));
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignPresentationSetSettings(const CampaignPresentationSettings* settings) {
    CampaignPresentationSettings candidate;
    if (!settings || settings->size < (uint32_t)sizeof(*settings)) return 0;

    PresentationLock();
    EnsureSettingsUnlocked();
    CopyBytes(&candidate, settings, (uint32_t)sizeof(candidate));
    candidate.size = (uint32_t)sizeof(candidate);
    candidate.version = CAMPAIGN_PRESENTATION_SETTINGS_VERSION;
    candidate.revision = g_settings.revision;
    candidate.checksum = SettingsChecksum(&candidate);

    if (!ValidateSettings(&candidate) ||
        !ApplyLegacyPresentationBindings(&candidate)) {
        PresentationUnlock();
        return 0;
    }

    CopyBytes(&g_settings, &candidate, (uint32_t)sizeof(g_settings));
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignPresentationResetSettings(void) {
    CampaignPresentationSettings defaults;
    int result;

    InitSettings(&defaults);

    PresentationLock();
    result = ApplyLegacyPresentationBindings(&defaults);
    if (result) {
        CopyBytes(&g_settings, &defaults, (uint32_t)sizeof(g_settings));
        InterlockedExchange(&g_settings_loaded, 1);
    }
    PresentationUnlock();
    return result;
}

static void ReplayReleaseUnlocked(void) {
    if (g_replay_samples) {
        VirtualFree(g_replay_samples, 0, MEM_RELEASE);
        g_replay_samples = 0;
    }
    g_replay_capacity = 0;
    g_replay_count = 0;
    g_replay_write = 0;
    g_replay_dropped = 0;
    g_replay_throttled = 0;
    g_replay_last_frame_time_ms = 0;
    g_replay_last_frame_valid = 0;
    g_replay_active = 0;
    g_replay_marker_count = 0;
    g_replay_dropped_markers = 0;
    ZeroBytes(&g_playback, (uint32_t)sizeof(g_playback));
    g_playback.size = (uint32_t)sizeof(g_playback);
    g_playback.speed_permille = 1000;
    ZeroBytes(&g_replay_metadata, (uint32_t)sizeof(g_replay_metadata));
    g_replay_metadata.size = (uint32_t)sizeof(g_replay_metadata);
    g_replay_metadata.version = CAMPAIGN_REPLAY_FORMAT_VERSION;
}

int __cdecl CampaignReplaySetMetadata(const CampaignReplayMetadata* metadata) {
    if (!metadata || metadata->size < (uint32_t)sizeof(*metadata)) return 0;
    if (metadata->version != CAMPAIGN_REPLAY_FORMAT_VERSION) return 0;
    if (metadata->event_id < 0 || metadata->track_id < 0 || metadata->player_car_id < 0) return 0;

    PresentationLock();
    CopyBytes(&g_replay_metadata, metadata, (uint32_t)sizeof(g_replay_metadata));
    g_replay_metadata.size = (uint32_t)sizeof(g_replay_metadata);
    g_replay_metadata.version = CAMPAIGN_REPLAY_FORMAT_VERSION;
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplayGetMetadata(CampaignReplayMetadata* out) {
    if (!out || out->size < (uint32_t)sizeof(*out)) return 0;

    PresentationLock();
    CopyBytes(out, &g_replay_metadata, (uint32_t)sizeof(g_replay_metadata));
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplayStart(uint32_t capacity) {
    SIZE_T bytes;

    if (capacity < RX_REPLAY_MIN_CAPACITY) capacity = RX_REPLAY_MIN_CAPACITY;
    if (capacity > RX_REPLAY_MAX_CAPACITY) capacity = RX_REPLAY_MAX_CAPACITY;

    PresentationLock();
    ReplayReleaseUnlocked();

    bytes = (SIZE_T)capacity * (SIZE_T)sizeof(CampaignReplaySample);
    g_replay_samples = (CampaignReplaySample*)VirtualAlloc(
        0, bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
    );
    if (!g_replay_samples) {
        PresentationUnlock();
        return 0;
    }

    g_replay_capacity = capacity;
    g_replay_active = 1;
    g_replay_metadata.size = (uint32_t)sizeof(g_replay_metadata);
    g_replay_metadata.version = CAMPAIGN_REPLAY_FORMAT_VERSION;
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplayStop(void) {
    PresentationLock();
    g_replay_active = 0;
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplayClear(void) {
    PresentationLock();
    g_replay_count = 0;
    g_replay_write = 0;
    g_replay_dropped = 0;
    g_replay_throttled = 0;
    g_replay_last_frame_time_ms = 0;
    g_replay_last_frame_valid = 0;
    g_replay_marker_count = 0;
    g_replay_dropped_markers = 0;
    PresentationUnlock();
    return 1;
}

static int ReplayRecordUnlocked(const CampaignReplaySample* sample) {
    if (!sample || !g_replay_active || !g_replay_samples || g_replay_capacity == 0) {
        return 0;
    }

    CopyBytes(
        &g_replay_samples[g_replay_write],
        sample,
        (uint32_t)sizeof(CampaignReplaySample)
    );

    g_replay_write = (g_replay_write + 1u) % g_replay_capacity;
    if (g_replay_count < g_replay_capacity) {
        ++g_replay_count;
    } else {
        ++g_replay_dropped;
    }
    return 1;
}

int __cdecl CampaignReplayRecord(const CampaignReplaySample* sample) {
    int result;
    if (!sample) return 0;

    PresentationLock();
    result = ReplayRecordUnlocked(sample);
    PresentationUnlock();
    return result;
}

int __cdecl CampaignReplayRecordFrame(const CampaignReplaySample* sample) {
    uint32_t delta;
    int result;

    if (!sample) return 0;

    PresentationLock();
    if (!g_replay_active || !g_replay_samples || g_replay_capacity == 0) {
        PresentationUnlock();
        return 0;
    }

    if (g_replay_last_frame_valid) {
        if (sample->time_ms >= g_replay_last_frame_time_ms) {
            delta = sample->time_ms - g_replay_last_frame_time_ms;
            if (delta < RX_REPLAY_FRAME_INTERVAL_MS) {
                ++g_replay_throttled;
                PresentationUnlock();
                return 1;
            }
        }
        /* A backwards race clock is treated as a new capture epoch. */
    }

    result = ReplayRecordUnlocked(sample);
    if (result) {
        g_replay_last_frame_time_ms = sample->time_ms;
        g_replay_last_frame_valid = 1;
    }
    PresentationUnlock();
    return result;
}

static uint32_t ReplayPhysicalIndexUnlocked(uint32_t chronological_index) {
    uint32_t first;
    if (g_replay_count < g_replay_capacity) return chronological_index;
    first = g_replay_write;
    return (first + chronological_index) % g_replay_capacity;
}

int __cdecl CampaignReplayGetInfo(CampaignReplayInfo* out) {
    uint32_t first_index;
    uint32_t last_index;

    if (!out || out->size < (uint32_t)sizeof(*out)) return 0;
    PresentationLock();

    out->size = (uint32_t)sizeof(*out);
    out->active = g_replay_active;
    out->sample_count = g_replay_count;
    out->capacity = g_replay_capacity;
    out->dropped_samples = g_replay_dropped;
    out->throttled_samples = g_replay_throttled;
    out->marker_count = g_replay_marker_count;
    out->dropped_markers = g_replay_dropped_markers;
    out->first_time_ms = 0;
    out->last_time_ms = 0;

    if (g_replay_samples && g_replay_count > 0) {
        first_index = ReplayPhysicalIndexUnlocked(0);
        last_index = ReplayPhysicalIndexUnlocked(g_replay_count - 1u);
        out->first_time_ms = g_replay_samples[first_index].time_ms;
        out->last_time_ms = g_replay_samples[last_index].time_ms;
    }

    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplayGetSample(uint32_t chronological_index, CampaignReplaySample* out) {
    uint32_t physical;
    if (!out) return 0;

    PresentationLock();
    if (!g_replay_samples || chronological_index >= g_replay_count) {
        PresentationUnlock();
        return 0;
    }

    physical = ReplayPhysicalIndexUnlocked(chronological_index);
    CopyBytes(out, &g_replay_samples[physical], (uint32_t)sizeof(*out));
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplayGetAutoPath(WCHAR* out, uint32_t capacity_chars) {
    int result = 0;

    if (!out || capacity_chars == 0) return 0;

    PresentationLock();
    if (g_replay_metadata.event_id > 0 &&
        g_replay_metadata.session_id != 0 &&
        BuildReplayAutoPathUnlocked()) {
        result = WideCopy(out, capacity_chars, g_replay_auto_path);
    }
    PresentationUnlock();
    return result;
}

int __cdecl CampaignReplaySaveAuto(void) {
    WCHAR path[1024];
    CampaignReplayInfo info;

    ZeroBytes(path, (uint32_t)sizeof(path));
    ZeroBytes(&info, (uint32_t)sizeof(info));
    info.size = (uint32_t)sizeof(info);

    /*
      Do not create empty replay files. START/FINISH metadata-only sessions are
      useful for lifecycle diagnostics but are not playable replays.
    */
    if (!CampaignReplayGetInfo(&info) || info.sample_count == 0) return 0;
    if (!CampaignReplayGetAutoPath(path, 1024)) return 0;
    return CampaignReplaySave(path);
}

int __cdecl CampaignReplaySave(const WCHAR* path) {
    HANDLE h;
    DWORD written;
    uint32_t i;
    uint32_t physical;
    uint32_t sample_hash = 2166136261u;
    CampaignReplayFileHeader header;
    WCHAR tmp_path[1024];

    if (!path || !path[0]) return 0;
    if (!WideCopy(tmp_path, 1024, path)) return 0;
    if (!WideAppend(tmp_path, 1024, L".tmp")) return 0;

    PresentationLock();
    if (!g_replay_samples || g_replay_count == 0) {
        PresentationUnlock();
        return 0;
    }

    ZeroBytes(&header, (uint32_t)sizeof(header));
    header.magic = RXRP_MAGIC;
    header.version = CAMPAIGN_REPLAY_FORMAT_VERSION;
    header.sample_size = (uint32_t)sizeof(CampaignReplaySample);
    header.sample_count = g_replay_count;
    header.marker_size = (uint32_t)sizeof(CampaignReplayMarker);
    header.marker_count = g_replay_marker_count;
    header.first_time_ms = g_replay_samples[ReplayPhysicalIndexUnlocked(0)].time_ms;
    header.last_time_ms = g_replay_samples[ReplayPhysicalIndexUnlocked(g_replay_count - 1u)].time_ms;

    for (i = 0; i < g_replay_count; ++i) {
        physical = ReplayPhysicalIndexUnlocked(i);
        sample_hash = HashUpdate(
            sample_hash,
            &g_replay_samples[physical],
            (uint32_t)sizeof(CampaignReplaySample)
        );
    }
    header.sample_hash = sample_hash;
    header.marker_hash = HashBytes(
        g_replay_markers,
        g_replay_marker_count * (uint32_t)sizeof(CampaignReplayMarker)
    );
    CopyBytes(&header.metadata, &g_replay_metadata, (uint32_t)sizeof(header.metadata));

    DeleteFileW(tmp_path);
    h = CreateFileW(tmp_path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) {
        PresentationUnlock();
        return 0;
    }

    written = 0;
    if (!WriteFile(h, &header, (DWORD)sizeof(header), &written, 0) ||
        written != (DWORD)sizeof(header)) {
        CloseHandle(h);
        DeleteFileW(tmp_path);
        PresentationUnlock();
        return 0;
    }

    for (i = 0; i < g_replay_count; ++i) {
        physical = ReplayPhysicalIndexUnlocked(i);
        written = 0;
        if (!WriteFile(
                h,
                &g_replay_samples[physical],
                (DWORD)sizeof(CampaignReplaySample),
                &written,
                0) ||
            written != (DWORD)sizeof(CampaignReplaySample)) {
            CloseHandle(h);
            DeleteFileW(tmp_path);
            PresentationUnlock();
            return 0;
        }
    }

    for (i = 0; i < g_replay_marker_count; ++i) {
        written = 0;
        if (!WriteFile(
                h,
                &g_replay_markers[i],
                (DWORD)sizeof(CampaignReplayMarker),
                &written,
                0) ||
            written != (DWORD)sizeof(CampaignReplayMarker)) {
            CloseHandle(h);
            DeleteFileW(tmp_path);
            PresentationUnlock();
            return 0;
        }
    }

    FlushFileBuffers(h);
    CloseHandle(h);

    if (!MoveFileExW(
            tmp_path,
            path,
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(tmp_path);
        PresentationUnlock();
        return 0;
    }

    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplayLoad(const WCHAR* path) {
    HANDLE h;
    DWORD got;
    CampaignReplayFileHeader header;
    CampaignReplaySample* samples;
    SIZE_T bytes;
    uint32_t i;
    uint32_t sample_hash;
    uint32_t marker_hash;

    if (!path || !path[0]) return 0;

    h = CreateFileW(
        path,
        GENERIC_READ,
        FILE_SHARE_READ,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );
    if (h == INVALID_HANDLE_VALUE) return 0;

    ZeroBytes(&header, (uint32_t)sizeof(header));
    got = 0;
    if (!ReadFile(h, &header, (DWORD)sizeof(header), &got, 0) ||
        got != (DWORD)sizeof(header) ||
        header.magic != RXRP_MAGIC ||
        header.version != CAMPAIGN_REPLAY_FORMAT_VERSION ||
        header.sample_size != (uint32_t)sizeof(CampaignReplaySample) ||
        header.marker_size != (uint32_t)sizeof(CampaignReplayMarker) ||
        header.sample_count == 0 ||
        header.sample_count > RX_REPLAY_MAX_CAPACITY ||
        header.marker_count > CAMPAIGN_REPLAY_MARKER_MAX ||
        header.metadata.size != (uint32_t)sizeof(CampaignReplayMetadata) ||
        header.metadata.version != CAMPAIGN_REPLAY_FORMAT_VERSION) {
        CloseHandle(h);
        return 0;
    }

    bytes = (SIZE_T)header.sample_count * (SIZE_T)sizeof(CampaignReplaySample);
    samples = (CampaignReplaySample*)VirtualAlloc(
        0, bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
    );
    if (!samples) {
        CloseHandle(h);
        return 0;
    }

    got = 0;
    if (!ReadFile(h, samples, (DWORD)bytes, &got, 0) || got != (DWORD)bytes) {
        VirtualFree(samples, 0, MEM_RELEASE);
        CloseHandle(h);
        return 0;
    }

    PresentationLock();
    ReplayReleaseUnlocked();
    g_replay_samples = samples;
    g_replay_capacity = header.sample_count;
    g_replay_count = header.sample_count;
    g_replay_write = 0;
    g_replay_active = 0;
    CopyBytes(&g_replay_metadata, &header.metadata, (uint32_t)sizeof(g_replay_metadata));

    for (i = 0; i < header.marker_count; ++i) {
        got = 0;
        if (!ReadFile(
                h,
                &g_replay_markers[i],
                (DWORD)sizeof(CampaignReplayMarker),
                &got,
                0) ||
            got != (DWORD)sizeof(CampaignReplayMarker)) {
            ReplayReleaseUnlocked();
            PresentationUnlock();
            CloseHandle(h);
            return 0;
        }
        ++g_replay_marker_count;
    }

    sample_hash = HashBytes(
        g_replay_samples,
        g_replay_count * (uint32_t)sizeof(CampaignReplaySample)
    );
    marker_hash = HashBytes(
        g_replay_markers,
        g_replay_marker_count * (uint32_t)sizeof(CampaignReplayMarker)
    );

    if (sample_hash != header.sample_hash || marker_hash != header.marker_hash) {
        ReplayReleaseUnlocked();
        PresentationUnlock();
        CloseHandle(h);
        return 0;
    }

    PresentationUnlock();
    CloseHandle(h);
    return 1;
}

int __cdecl CampaignReplayAddMarker(const CampaignReplayMarker* marker) {
    if (!marker || marker->type == 0) return 0;

    PresentationLock();
    if (g_replay_marker_count >= CAMPAIGN_REPLAY_MARKER_MAX) {
        ++g_replay_dropped_markers;
        PresentationUnlock();
        return 0;
    }

    CopyBytes(
        &g_replay_markers[g_replay_marker_count],
        marker,
        (uint32_t)sizeof(CampaignReplayMarker)
    );
    ++g_replay_marker_count;
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplayGetMarker(uint32_t index, CampaignReplayMarker* out) {
    if (!out) return 0;

    PresentationLock();
    if (index >= g_replay_marker_count) {
        PresentationUnlock();
        return 0;
    }

    CopyBytes(out, &g_replay_markers[index], (uint32_t)sizeof(*out));
    PresentationUnlock();
    return 1;
}

static void ReplayRefreshPlaybackBoundsUnlocked(void) {
    uint32_t first_index;
    uint32_t last_index;

    g_playback.size = (uint32_t)sizeof(g_playback);
    g_playback.loaded = (g_replay_samples && g_replay_count > 0) ? 1u : 0u;

    if (!g_playback.loaded) {
        g_playback.playing = 0;
        g_playback.current_time_ms = 0;
        g_playback.first_time_ms = 0;
        g_playback.last_time_ms = 0;
        g_playback.selected_marker = 0;
        if (g_playback.speed_permille == 0) g_playback.speed_permille = 1000;
        return;
    }

    first_index = ReplayPhysicalIndexUnlocked(0);
    last_index = ReplayPhysicalIndexUnlocked(g_replay_count - 1u);
    g_playback.first_time_ms = g_replay_samples[first_index].time_ms;
    g_playback.last_time_ms = g_replay_samples[last_index].time_ms;

    if (g_playback.current_time_ms < g_playback.first_time_ms ||
        g_playback.current_time_ms > g_playback.last_time_ms) {
        g_playback.current_time_ms = g_playback.first_time_ms;
    }
    if (g_playback.speed_permille == 0) g_playback.speed_permille = 1000;
}

int __cdecl CampaignReplayPlay(void) {
    PresentationLock();
    ReplayRefreshPlaybackBoundsUnlocked();
    if (!g_playback.loaded) {
        PresentationUnlock();
        return 0;
    }
    g_playback.playing = 1;
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplayPause(void) {
    PresentationLock();
    ReplayRefreshPlaybackBoundsUnlocked();
    g_playback.playing = 0;
    PresentationUnlock();
    return g_playback.loaded ? 1 : 0;
}

int __cdecl CampaignReplaySeek(uint32_t time_ms) {
    PresentationLock();
    ReplayRefreshPlaybackBoundsUnlocked();
    if (!g_playback.loaded ||
        time_ms < g_playback.first_time_ms ||
        time_ms > g_playback.last_time_ms) {
        PresentationUnlock();
        return 0;
    }
    g_playback.current_time_ms = time_ms;
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplaySetSpeed(uint32_t speed_permille) {
    switch (speed_permille) {
    case 100:
    case 250:
    case 500:
    case 1000:
    case 2000:
    case 4000:
        break;
    default:
        return 0;
    }

    PresentationLock();
    g_playback.speed_permille = speed_permille;
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplayGetPlaybackState(CampaignReplayPlaybackState* out) {
    if (!out || out->size < (uint32_t)sizeof(*out)) return 0;

    PresentationLock();
    ReplayRefreshPlaybackBoundsUnlocked();
    CopyBytes(out, &g_playback, (uint32_t)sizeof(g_playback));
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplayGetSampleAtTime(
    uint32_t time_ms,
    int32_t entity_id,
    CampaignReplaySample* out
) {
    uint32_t i;
    uint32_t physical;
    uint32_t best_delta = 0xFFFFFFFFu;
    int found = 0;

    if (!out) return 0;

    PresentationLock();
    if (!g_replay_samples || g_replay_count == 0) {
        PresentationUnlock();
        return 0;
    }

    for (i = 0; i < g_replay_count; ++i) {
        uint32_t delta;
        physical = ReplayPhysicalIndexUnlocked(i);

        if (entity_id != 0 && g_replay_samples[physical].entity_id != entity_id) {
            continue;
        }

        if (g_replay_samples[physical].time_ms > time_ms) {
            delta = g_replay_samples[physical].time_ms - time_ms;
        } else {
            delta = time_ms - g_replay_samples[physical].time_ms;
        }

        if (!found || delta < best_delta) {
            best_delta = delta;
            CopyBytes(out, &g_replay_samples[physical], (uint32_t)sizeof(*out));
            found = 1;
            if (delta == 0) break;
        }
    }

    PresentationUnlock();
    return found;
}

int __cdecl CampaignReplayNextMarker(uint32_t from_time_ms, CampaignReplayMarker* out) {
    uint32_t i;
    uint32_t best_time = 0xFFFFFFFFu;
    int found = 0;

    if (!out) return 0;

    PresentationLock();
    for (i = 0; i < g_replay_marker_count; ++i) {
        if (g_replay_markers[i].time_ms > from_time_ms &&
            (!found || g_replay_markers[i].time_ms < best_time)) {
            best_time = g_replay_markers[i].time_ms;
            CopyBytes(out, &g_replay_markers[i], (uint32_t)sizeof(*out));
            g_playback.selected_marker = i;
            found = 1;
        }
    }
    PresentationUnlock();
    return found;
}

int __cdecl CampaignReplayPreviousMarker(uint32_t from_time_ms, CampaignReplayMarker* out) {
    uint32_t i;
    uint32_t best_time = 0;
    int found = 0;

    if (!out) return 0;

    PresentationLock();
    for (i = 0; i < g_replay_marker_count; ++i) {
        if (g_replay_markers[i].time_ms < from_time_ms &&
            (!found || g_replay_markers[i].time_ms > best_time)) {
            best_time = g_replay_markers[i].time_ms;
            CopyBytes(out, &g_replay_markers[i], (uint32_t)sizeof(*out));
            g_playback.selected_marker = i;
            found = 1;
        }
    }
    PresentationUnlock();
    return found;
}

int __cdecl CampaignReplayAdvance(uint32_t real_delta_ms) {
    uint64_t scaled;
    uint64_t next;

    PresentationLock();
    ReplayRefreshPlaybackBoundsUnlocked();
    if (!g_playback.loaded || !g_playback.playing) {
        PresentationUnlock();
        return 0;
    }

    scaled = ((uint64_t)real_delta_ms * (uint64_t)g_playback.speed_permille) / 1000u;
    next = (uint64_t)g_playback.current_time_ms + scaled;

    if (next >= g_playback.last_time_ms) {
        g_playback.current_time_ms = g_playback.last_time_ms;
        g_playback.playing = 0;
    } else {
        g_playback.current_time_ms = (uint32_t)next;
    }

    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplayStep(int32_t direction, int32_t entity_id) {
    uint32_t i;
    uint32_t physical;
    uint32_t selected_time = 0;
    int found = 0;

    if (direction == 0) return 0;

    PresentationLock();
    ReplayRefreshPlaybackBoundsUnlocked();
    if (!g_playback.loaded) {
        PresentationUnlock();
        return 0;
    }

    for (i = 0; i < g_replay_count; ++i) {
        uint32_t t;
        physical = ReplayPhysicalIndexUnlocked(i);
        if (entity_id != 0 && g_replay_samples[physical].entity_id != entity_id) {
            continue;
        }

        t = g_replay_samples[physical].time_ms;
        if (direction > 0) {
            if (t > g_playback.current_time_ms &&
                (!found || t < selected_time)) {
                selected_time = t;
                found = 1;
            }
        } else {
            if (t < g_playback.current_time_ms &&
                (!found || t > selected_time)) {
                selected_time = t;
                found = 1;
            }
        }
    }

    if (found) {
        g_playback.current_time_ms = selected_time;
        g_playback.playing = 0;
    }

    PresentationUnlock();
    return found;
}

static int ReplayLibraryHeaderValid(
    const CampaignReplayFileHeader* header,
    const WIN32_FIND_DATAW* find_data
) {
    ULARGE_INTEGER file_size;
    ULARGE_INTEGER expected;

    if (!header || !find_data) return 0;
    if (header->magic != RXRP_MAGIC) return 0;
    if (header->version != CAMPAIGN_REPLAY_FORMAT_VERSION) return 0;
    if (header->sample_size != (uint32_t)sizeof(CampaignReplaySample)) return 0;
    if (header->marker_size != (uint32_t)sizeof(CampaignReplayMarker)) return 0;
    if (header->sample_count == 0 || header->sample_count > RX_REPLAY_MAX_CAPACITY) return 0;
    if (header->marker_count > CAMPAIGN_REPLAY_MARKER_MAX) return 0;
    if (header->metadata.size != (uint32_t)sizeof(CampaignReplayMetadata)) return 0;
    if (header->metadata.version != CAMPAIGN_REPLAY_FORMAT_VERSION) return 0;

    file_size.LowPart = find_data->nFileSizeLow;
    file_size.HighPart = find_data->nFileSizeHigh;

    expected.QuadPart = (ULONGLONG)sizeof(CampaignReplayFileHeader);
    expected.QuadPart += (ULONGLONG)header->sample_count *
        (ULONGLONG)sizeof(CampaignReplaySample);
    expected.QuadPart += (ULONGLONG)header->marker_count *
        (ULONGLONG)sizeof(CampaignReplayMarker);

    return file_size.QuadPart == expected.QuadPart ? 1 : 0;
}

static int ReadReplayLibraryEntryUnlocked(
    const WCHAR* filename,
    const WIN32_FIND_DATAW* find_data,
    CampaignReplayLibraryEntry* out
) {
    HANDLE h;
    DWORD got = 0;
    CampaignReplayFileHeader header;

    if (!filename || !find_data || !out) return 0;
    if (!BuildReplayDirectoryUnlocked()) return 0;

    ZeroBytes(g_replay_library_path, (uint32_t)sizeof(g_replay_library_path));
    if (!WideCopy(g_replay_library_path, 1024, g_replay_auto_dir)) return 0;
    if (!WideAppend(g_replay_library_path, 1024, L"\\")) return 0;
    if (!WideAppend(g_replay_library_path, 1024, filename)) return 0;

    h = CreateFileW(
        g_replay_library_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );
    if (h == INVALID_HANDLE_VALUE) return 0;

    ZeroBytes(&header, (uint32_t)sizeof(header));
    if (!ReadFile(h, &header, (DWORD)sizeof(header), &got, 0) ||
        got != (DWORD)sizeof(header)) {
        CloseHandle(h);
        return 0;
    }
    CloseHandle(h);

    if (!ReplayLibraryHeaderValid(&header, find_data)) return 0;

    ZeroBytes(out, (uint32_t)sizeof(*out));
    out->size = (uint32_t)sizeof(*out);
    if (!WideCopy(
            out->filename,
            CAMPAIGN_REPLAY_FILENAME_MAX,
            filename)) {
        return 0;
    }

    CopyBytes(&out->metadata, &header.metadata, (uint32_t)sizeof(out->metadata));
    out->sample_count = header.sample_count;
    out->marker_count = header.marker_count;
    out->first_time_ms = header.first_time_ms;
    out->last_time_ms = header.last_time_ms;
    out->duration_ms = header.last_time_ms >= header.first_time_ms ?
        header.last_time_ms - header.first_time_ms : 0;
    out->file_size_low = find_data->nFileSizeLow;
    out->file_size_high = find_data->nFileSizeHigh;
    out->modified_time_low = find_data->ftLastWriteTime.dwLowDateTime;
    out->modified_time_high = find_data->ftLastWriteTime.dwHighDateTime;
    return 1;
}

static int ReplayLibraryEntryNewer(
    const CampaignReplayLibraryEntry* a,
    const CampaignReplayLibraryEntry* b
) {
    if (a->modified_time_high != b->modified_time_high) {
        return a->modified_time_high > b->modified_time_high;
    }
    return a->modified_time_low > b->modified_time_low;
}

int __cdecl CampaignReplayLibraryRefresh(void) {
    WIN32_FIND_DATAW find_data;
    HANDLE find;
    CampaignReplayLibraryEntry candidate;
    uint32_t i;

    PresentationLock();
    ZeroBytes(g_replay_library, (uint32_t)sizeof(g_replay_library));
    g_replay_library_count = 0;

    if (!BuildReplayDirectoryUnlocked()) {
        PresentationUnlock();
        return 0;
    }

    ZeroBytes(g_replay_library_pattern, (uint32_t)sizeof(g_replay_library_pattern));
    if (!WideCopy(g_replay_library_pattern, 1024, g_replay_auto_dir) ||
        !WideAppend(g_replay_library_pattern, 1024, L"\\*.rexreplay")) {
        PresentationUnlock();
        return 0;
    }

    ZeroBytes(&find_data, (uint32_t)sizeof(find_data));
    find = FindFirstFileW(g_replay_library_pattern, &find_data);
    if (find == INVALID_HANDLE_VALUE) {
        DWORD err = GetLastError();
        PresentationUnlock();
        return err == ERROR_FILE_NOT_FOUND ? 1 : 0;
    }

    do {
        if (!(find_data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) &&
            g_replay_library_count < CAMPAIGN_REPLAY_LIBRARY_MAX) {
            ZeroBytes(&candidate, (uint32_t)sizeof(candidate));
            if (ReadReplayLibraryEntryUnlocked(
                    find_data.cFileName,
                    &find_data,
                    &candidate)) {
                uint32_t pos = g_replay_library_count;
                while (pos > 0 &&
                       ReplayLibraryEntryNewer(
                           &candidate,
                           &g_replay_library[pos - 1u])) {
                    CopyBytes(
                        &g_replay_library[pos],
                        &g_replay_library[pos - 1u],
                        (uint32_t)sizeof(CampaignReplayLibraryEntry)
                    );
                    --pos;
                }
                CopyBytes(
                    &g_replay_library[pos],
                    &candidate,
                    (uint32_t)sizeof(CampaignReplayLibraryEntry)
                );
                ++g_replay_library_count;
            }
        }
    } while (FindNextFileW(find, &find_data));

    FindClose(find);
    PresentationUnlock();
    return 1;
}

uint32_t __cdecl CampaignReplayLibraryCount(void) {
    uint32_t count;
    PresentationLock();
    count = g_replay_library_count;
    PresentationUnlock();
    return count;
}

int __cdecl CampaignReplayLibraryGet(
    uint32_t index,
    CampaignReplayLibraryEntry* out
) {
    if (!out || out->size < (uint32_t)sizeof(*out)) return 0;

    PresentationLock();
    if (index >= g_replay_library_count) {
        PresentationUnlock();
        return 0;
    }
    CopyBytes(
        out,
        &g_replay_library[index],
        (uint32_t)sizeof(CampaignReplayLibraryEntry)
    );
    PresentationUnlock();
    return 1;
}

static int ReplayLibraryBuildIndexedPath(
    uint32_t index,
    WCHAR* out,
    uint32_t capacity_chars
) {
    int result = 0;

    if (!out || capacity_chars == 0) return 0;

    PresentationLock();
    if (index < g_replay_library_count &&
        BuildReplayDirectoryUnlocked() &&
        WideCopy(out, capacity_chars, g_replay_auto_dir) &&
        WideAppend(out, capacity_chars, L"\\") &&
        WideAppend(
            out,
            capacity_chars,
            g_replay_library[index].filename)) {
        result = 1;
    }
    PresentationUnlock();
    return result;
}

int __cdecl CampaignReplayLibraryLoad(uint32_t index) {
    WCHAR path[1024];
    ZeroBytes(path, (uint32_t)sizeof(path));
    if (!ReplayLibraryBuildIndexedPath(index, path, 1024)) return 0;
    return CampaignReplayLoad(path);
}

int __cdecl CampaignReplayLibraryDelete(uint32_t index) {
    WCHAR path[1024];
    int result;

    ZeroBytes(path, (uint32_t)sizeof(path));
    if (!ReplayLibraryBuildIndexedPath(index, path, 1024)) return 0;

    result = DeleteFileW(path) ? 1 : 0;
    if (result) CampaignReplayLibraryRefresh();
    return result;
}

int __cdecl CampaignPhotoEnter(const CampaignPhotoState* initial) {
    CampaignPhotoState candidate;
    CampaignPhotoState restore;

    ZeroBytes(&restore, (uint32_t)sizeof(restore));
    restore.size = (uint32_t)sizeof(restore);

    if (!CampaignPhotoBindingsReady(CAMPAIGN_PHOTO_CAMERA_FREE) ||
        !CampaignPhotoBindingsRead(&restore)) {
        return 0;
    }

    CopyBytes(&candidate, &restore, (uint32_t)sizeof(candidate));
    candidate.size = (uint32_t)sizeof(candidate);
    candidate.active = 1;
    candidate.camera_mode = CAMPAIGN_PHOTO_CAMERA_FREE;
    candidate.hide_hud = 1;

    if (initial && initial->size >= (uint32_t)sizeof(*initial)) {
        CopyBytes(&candidate, initial, (uint32_t)sizeof(candidate));
        candidate.size = (uint32_t)sizeof(candidate);
        candidate.active = 1;
    }

    if (candidate.camera_mode != CAMPAIGN_PHOTO_CAMERA_FREE) return 0;

    restore.active = 1;
    restore.camera_mode = CAMPAIGN_PHOTO_CAMERA_FREE;

    PresentationLock();
    CopyBytes(&g_photo_restore, &restore, (uint32_t)sizeof(g_photo_restore));
    g_photo_restore_valid = 1;
    CopyBytes(&g_photo, &candidate, (uint32_t)sizeof(g_photo));
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignPhotoExit(void) {
    CampaignPhotoState restore;
    int should_restore = 0;

    ZeroBytes(&restore, (uint32_t)sizeof(restore));

    PresentationLock();
    if (g_photo_restore_valid) {
        CopyBytes(&restore, &g_photo_restore, (uint32_t)sizeof(restore));
        should_restore = 1;
    }
    PresentationUnlock();

    if (should_restore && !CampaignPhotoBindingsApply(&restore)) {
        return 0;
    }

    PresentationLock();
    ZeroBytes(&g_photo, (uint32_t)sizeof(g_photo));
    g_photo.size = (uint32_t)sizeof(g_photo);
    ZeroBytes(&g_photo_restore, (uint32_t)sizeof(g_photo_restore));
    g_photo_restore.size = (uint32_t)sizeof(g_photo_restore);
    g_photo_restore_valid = 0;
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignPhotoGet(CampaignPhotoState* out) {
    if (!out || out->size < (uint32_t)sizeof(*out)) return 0;
    PresentationLock();
    CopyBytes(out, &g_photo, (uint32_t)sizeof(g_photo));
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignPhotoSet(const CampaignPhotoState* state) {
    if (!state || state->size < (uint32_t)sizeof(*state)) return 0;
    if (state->camera_mode > CAMPAIGN_PHOTO_CAMERA_ORBIT) return 0;
    if (state->fov_x100 < 0) return 0;
    if (state->active &&
        (state->camera_mode != CAMPAIGN_PHOTO_CAMERA_FREE ||
         !CampaignPhotoBindingsReady(state->camera_mode))) {
        return 0;
    }

    PresentationLock();
    CopyBytes(&g_photo, state, (uint32_t)sizeof(g_photo));
    g_photo.size = (uint32_t)sizeof(g_photo);
    PresentationUnlock();
    return 1;
}

static int PhotoApplyAndCommit(const CampaignPhotoState* candidate) {
    if (!candidate || !candidate->active ||
        candidate->camera_mode != CAMPAIGN_PHOTO_CAMERA_FREE) {
        return 0;
    }

    if (!CampaignPhotoBindingsReady(candidate->camera_mode) ||
        !CampaignPhotoBindingsApply(candidate)) {
        return 0;
    }

    PresentationLock();
    CopyBytes(&g_photo, candidate, (uint32_t)sizeof(g_photo));
    g_photo.size = (uint32_t)sizeof(g_photo);
    PresentationUnlock();
    return 1;
}

static int AddI32Checked(int32_t value, int32_t delta, int32_t* out) {
    int64_t sum;
    if (!out) return 0;
    sum = (int64_t)value + (int64_t)delta;
    if (sum < -2147483647LL - 1LL || sum > 2147483647LL) return 0;
    *out = (int32_t)sum;
    return 1;
}

int __cdecl CampaignPhotoMove(
    int32_t dx_x1000,
    int32_t dy_x1000,
    int32_t dz_x1000
) {
    CampaignPhotoState candidate;

    ZeroBytes(&candidate, (uint32_t)sizeof(candidate));

    PresentationLock();
    if (!g_photo.active) {
        PresentationUnlock();
        return 0;
    }
    CopyBytes(&candidate, &g_photo, (uint32_t)sizeof(candidate));
    PresentationUnlock();

    candidate.position_x += (float)dx_x1000 / 1000.0f;
    candidate.position_y += (float)dy_x1000 / 1000.0f;
    candidate.position_z += (float)dz_x1000 / 1000.0f;
    return PhotoApplyAndCommit(&candidate);
}

int __cdecl CampaignPhotoRotate(
    int32_t pitch_delta_x100,
    int32_t yaw_delta_x100,
    int32_t roll_delta_x100
) {
    CampaignPhotoState candidate;
    int32_t pitch, yaw, roll;

    ZeroBytes(&candidate, (uint32_t)sizeof(candidate));

    PresentationLock();
    if (!g_photo.active) {
        PresentationUnlock();
        return 0;
    }
    CopyBytes(&candidate, &g_photo, (uint32_t)sizeof(candidate));
    PresentationUnlock();

    if (!AddI32Checked(candidate.pitch_x100, pitch_delta_x100, &pitch) ||
        !AddI32Checked(candidate.yaw_x100, yaw_delta_x100, &yaw) ||
        !AddI32Checked(candidate.roll_x100, roll_delta_x100, &roll)) {
        return 0;
    }

    candidate.pitch_x100 = pitch;
    candidate.yaw_x100 = yaw;
    candidate.roll_x100 = roll;
    return PhotoApplyAndCommit(&candidate);
}

int __cdecl CampaignPhotoSetFov(int32_t fov_x100) {
    CampaignPhotoState candidate;

    if (fov_x100 <= 0) return 0;
    ZeroBytes(&candidate, (uint32_t)sizeof(candidate));

    PresentationLock();
    if (!g_photo.active) {
        PresentationUnlock();
        return 0;
    }
    CopyBytes(&candidate, &g_photo, (uint32_t)sizeof(candidate));
    PresentationUnlock();

    candidate.fov_x100 = fov_x100;
    return PhotoApplyAndCommit(&candidate);
}

int __cdecl CampaignPhotoSetMoveSpeed(int32_t speed_x1000) {
    if (speed_x1000 <= 0) return 0;

    PresentationLock();
    if (!g_photo.active) {
        PresentationUnlock();
        return 0;
    }
    g_photo.move_speed_x1000 = speed_x1000;
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignPhotoResetView(void) {
    CampaignPhotoState candidate;
    uint32_t hide_hud;
    int32_t move_speed;

    ZeroBytes(&candidate, (uint32_t)sizeof(candidate));

    PresentationLock();
    if (!g_photo.active || !g_photo_restore_valid) {
        PresentationUnlock();
        return 0;
    }

    hide_hud = g_photo.hide_hud;
    move_speed = g_photo.move_speed_x1000;
    CopyBytes(&candidate, &g_photo_restore, (uint32_t)sizeof(candidate));
    PresentationUnlock();

    candidate.size = (uint32_t)sizeof(candidate);
    candidate.active = 1;
    candidate.camera_mode = CAMPAIGN_PHOTO_CAMERA_FREE;
    candidate.hide_hud = hide_hud;
    candidate.move_speed_x1000 = move_speed;
    return PhotoApplyAndCommit(&candidate);
}

int __cdecl CampaignPresentationGetDiagnostics(CampaignPresentationDiagnostics* out) {
    if (!out || out->size < (uint32_t)sizeof(*out)) return 0;

    PresentationLock();
    EnsureSettingsUnlocked();
    ReplayRefreshPlaybackBoundsUnlocked();

    out->size = (uint32_t)sizeof(*out);
    out->settings_revision = g_settings.revision;
    out->verified_capability_count = CampaignPresentationCatalogCount();
    out->verified_binding_count = CampaignPresentationBindingsCount();
    out->replay_recording = g_replay_active;
    out->replay_sample_count = g_replay_count;
    out->replay_marker_count = g_replay_marker_count;
    out->replay_loaded = g_playback.loaded;
    out->replay_playing = g_playback.playing;
    out->replay_time_ms = g_playback.current_time_ms;
    out->photo_active = g_photo.active;
    out->photo_camera_mode = g_photo.camera_mode;
    out->photo_binding_count = CampaignPhotoBindingsCount();
    out->photo_free_camera_ready =
        CampaignPhotoBindingsReady(CAMPAIGN_PHOTO_CAMERA_FREE) ? 1u : 0u;
    out->replay_binding_count = CampaignReplayBindingsCount();
    out->replay_recording_ready = CampaignReplayBindingsReady() ? 1u : 0u;
    out->original_ui_binding_count = CampaignOriginalUiBindingsCount();
    out->original_ui_feature_mask = 0u;
    if (CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_GRAPHICS_SETTINGS)) out->original_ui_feature_mask |= 1u << 0;
    if (CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_CAMERA_SETTINGS)) out->original_ui_feature_mask |= 1u << 1;
    if (CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_REPLAY)) out->original_ui_feature_mask |= 1u << 2;
    if (CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_PHOTO_MODE)) out->original_ui_feature_mask |= 1u << 3;
    if (CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_RACE_HUD)) out->original_ui_feature_mask |= 1u << 4;
    out->race_hud_binding_count = CampaignRaceHudBindingsCount();
    out->race_hud_original_ui_ready =
        CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_RACE_HUD) ? 1u : 0u;

    PresentationUnlock();
    return 1;
}

int __cdecl CampaignPresentationInvoke(CampaignPresentationCommand* command) {
    if (!command || command->size < (uint32_t)sizeof(*command)) return 0;

    command->status = 0;
    command->out0 = 0;
    command->out1 = 0;
    command->out2 = 0;

    switch (command->op) {
    case CAMPAIGN_PRESENTATION_OP_LOAD_SETTINGS:
        command->status = CampaignPresentationLoadSettings();
        break;
    case CAMPAIGN_PRESENTATION_OP_SAVE_SETTINGS:
        command->status = CampaignPresentationSaveSettings();
        break;
    case CAMPAIGN_PRESENTATION_OP_GET_SETTINGS:
        command->status = CampaignPresentationGetSettings(
            (CampaignPresentationSettings*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_SET_SETTINGS:
        command->status = CampaignPresentationSetSettings(
            (const CampaignPresentationSettings*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_RESET_SETTINGS:
        command->status = CampaignPresentationResetSettings();
        break;

    case CAMPAIGN_PRESENTATION_OP_CAPABILITY_RELOAD:
        command->status = CampaignPresentationCatalogLoad();
        command->out0 = (int32_t)CampaignPresentationCatalogCount();
        break;
    case CAMPAIGN_PRESENTATION_OP_CAPABILITY_COUNT:
        command->out0 = (int32_t)CampaignPresentationCatalogCount();
        command->status = 1;
        break;
    case CAMPAIGN_PRESENTATION_OP_CAPABILITY_GET:
        {
            const CampaignPresentationCapability* capability;
            capability = CampaignPresentationCatalogGet((uint32_t)command->a);
            if (!capability || !command->ptr0) break;
            CopyBytes(
                (void*)(uintptr_t)command->ptr0,
                capability,
                (uint32_t)sizeof(CampaignPresentationCapability)
            );
            command->status = 1;
        }
        break;
    case CAMPAIGN_PRESENTATION_OP_CAPABILITY_GET_VALUE:
        command->status = CampaignPresentationCatalogGetValue(
            (uint32_t)command->a,
            &command->out0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_CAPABILITY_SET_VALUE:
        command->status = CampaignPresentationCatalogSetValue(
            (uint32_t)command->a,
            command->b
        );
        if (command->status) command->out0 = command->b;
        break;
    case CAMPAIGN_PRESENTATION_OP_CAPABILITY_RESET_VALUE:
        command->status = CampaignPresentationCatalogResetValue(
            (uint32_t)command->a
        );
        if (command->status) {
            CampaignPresentationCatalogGetValue((uint32_t)command->a, &command->out0);
        }
        break;

    case CAMPAIGN_PRESENTATION_OP_REPLAY_GET_AUTO_PATH:
        command->status = CampaignReplayGetAutoPath(
            (WCHAR*)(uintptr_t)command->ptr0,
            (uint32_t)command->a
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_SAVE_AUTO:
        command->status = CampaignReplaySaveAuto();
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_SET_METADATA:
        command->status = CampaignReplaySetMetadata(
            (const CampaignReplayMetadata*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_GET_METADATA:
        command->status = CampaignReplayGetMetadata(
            (CampaignReplayMetadata*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_START:
        command->status = CampaignReplayStart((uint32_t)command->a);
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_STOP:
        command->status = CampaignReplayStop();
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_CLEAR:
        command->status = CampaignReplayClear();
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_RECORD:
        command->status = CampaignReplayRecord(
            (const CampaignReplaySample*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_INFO:
        command->status = CampaignReplayGetInfo(
            (CampaignReplayInfo*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_GET_SAMPLE:
        command->status = CampaignReplayGetSample(
            (uint32_t)command->a,
            (CampaignReplaySample*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_SAVE:
        command->status = CampaignReplaySave(
            (const WCHAR*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_LOAD:
        command->status = CampaignReplayLoad(
            (const WCHAR*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_ADD_MARKER:
        command->status = CampaignReplayAddMarker(
            (const CampaignReplayMarker*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_GET_MARKER:
        command->status = CampaignReplayGetMarker(
            (uint32_t)command->a,
            (CampaignReplayMarker*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_PLAY:
        command->status = CampaignReplayPlay();
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_PAUSE:
        command->status = CampaignReplayPause();
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_SEEK:
        command->status = CampaignReplaySeek((uint32_t)command->a);
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_SET_SPEED:
        command->status = CampaignReplaySetSpeed((uint32_t)command->a);
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_PLAYBACK_STATE:
        command->status = CampaignReplayGetPlaybackState(
            (CampaignReplayPlaybackState*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_SAMPLE_AT_TIME:
        command->status = CampaignReplayGetSampleAtTime(
            (uint32_t)command->a,
            command->b,
            (CampaignReplaySample*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_NEXT_MARKER:
        command->status = CampaignReplayNextMarker(
            (uint32_t)command->a,
            (CampaignReplayMarker*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_PREVIOUS_MARKER:
        command->status = CampaignReplayPreviousMarker(
            (uint32_t)command->a,
            (CampaignReplayMarker*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_ADVANCE:
        command->status = CampaignReplayAdvance((uint32_t)command->a);
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_STEP:
        command->status = CampaignReplayStep(command->a, command->b);
        break;

    case CAMPAIGN_PRESENTATION_OP_PHOTO_ENTER:
        command->status = CampaignPhotoEnter(
            (const CampaignPhotoState*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_PHOTO_EXIT:
        command->status = CampaignPhotoExit();
        break;
    case CAMPAIGN_PRESENTATION_OP_PHOTO_GET:
        command->status = CampaignPhotoGet(
            (CampaignPhotoState*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_PHOTO_SET:
        command->status = CampaignPhotoSet(
            (const CampaignPhotoState*)(uintptr_t)command->ptr0
        );
        break;

    case CAMPAIGN_PRESENTATION_OP_PHOTO_MOVE:
        command->status = CampaignPhotoMove(command->a, command->b, command->c);
        break;
    case CAMPAIGN_PRESENTATION_OP_PHOTO_ROTATE:
        command->status = CampaignPhotoRotate(command->a, command->b, command->c);
        break;
    case CAMPAIGN_PRESENTATION_OP_PHOTO_SET_FOV:
        command->status = CampaignPhotoSetFov(command->a);
        break;
    case CAMPAIGN_PRESENTATION_OP_PHOTO_SET_SPEED:
        command->status = CampaignPhotoSetMoveSpeed(command->a);
        break;
    case CAMPAIGN_PRESENTATION_OP_PHOTO_RESET_VIEW:
        command->status = CampaignPhotoResetView();
        break;

    case CAMPAIGN_PRESENTATION_OP_REPLAY_LIBRARY_REFRESH:
        command->status = CampaignReplayLibraryRefresh();
        command->out0 = (int32_t)CampaignReplayLibraryCount();
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_LIBRARY_COUNT:
        command->out0 = (int32_t)CampaignReplayLibraryCount();
        command->status = 1;
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_LIBRARY_GET:
        command->status = CampaignReplayLibraryGet(
            (uint32_t)command->a,
            (CampaignReplayLibraryEntry*)(uintptr_t)command->ptr0
        );
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_LIBRARY_LOAD:
        command->status = CampaignReplayLibraryLoad((uint32_t)command->a);
        break;
    case CAMPAIGN_PRESENTATION_OP_REPLAY_LIBRARY_DELETE:
        command->status = CampaignReplayLibraryDelete((uint32_t)command->a);
        if (command->status) {
            command->out0 = (int32_t)CampaignReplayLibraryCount();
        }
        break;

    case CAMPAIGN_PRESENTATION_OP_DIAGNOSTICS:
        command->status = CampaignPresentationGetDiagnostics(
            (CampaignPresentationDiagnostics*)(uintptr_t)command->ptr0
        );
        break;

    case CAMPAIGN_PRESENTATION_OP_ORIGINAL_UI_RELOAD:
        command->status = CampaignOriginalUiBindingsLoad();
        command->out0 = (int32_t)CampaignOriginalUiBindingsCount();
        break;
    case CAMPAIGN_PRESENTATION_OP_ORIGINAL_UI_COUNT:
        command->out0 = (int32_t)CampaignOriginalUiBindingsCount();
        command->status = 1;
        break;
    case CAMPAIGN_PRESENTATION_OP_ORIGINAL_UI_FEATURE_READY:
        command->out0 = CampaignOriginalUiFeatureReady((uint32_t)command->a) ? 1 : 0;
        command->status = 1;
        break;

    case CAMPAIGN_PRESENTATION_OP_RACE_HUD_RELOAD:
        command->status = CampaignRaceHudBindingsLoad();
        command->out0 = (int32_t)CampaignRaceHudBindingsCount();
        break;
    case CAMPAIGN_PRESENTATION_OP_RACE_HUD_COUNT:
        command->out0 = (int32_t)CampaignRaceHudBindingsCount();
        command->status = 1;
        break;
    case CAMPAIGN_PRESENTATION_OP_RACE_HUD_ELEMENT_READY:
        command->out0 = CampaignRaceHudElementReady(
            (uint32_t)command->a,
            (uint32_t)command->b
        ) ? 1 : 0;
        command->status = 1;
        break;
    case CAMPAIGN_PRESENTATION_OP_RACE_HUD_APPLY_ELEMENT:
        command->status = CampaignRaceHudApplyElement(
            (const CampaignRaceHudElementState*)(uintptr_t)command->ptr0
        );
        break;
    default:
        return 0;
    }

    return command->status ? 1 : 0;
}
