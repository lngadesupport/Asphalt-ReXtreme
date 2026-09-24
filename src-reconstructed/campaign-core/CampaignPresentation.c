#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignPresentation.h"

#define RXPS_MAGIC 0x53505852u /* RXPS */
#define RXRP_MAGIC 0x50525852u /* RXRP */
#define RX_REPLAY_MIN_CAPACITY 256u
#define RX_REPLAY_MAX_CAPACITY 524288u

typedef struct CampaignPresentationDisk {
    uint32_t magic;
    CampaignPresentationSettings settings;
} CampaignPresentationDisk;

typedef struct CampaignReplayFileHeader {
    uint32_t magic;
    uint32_t version;
    uint32_t sample_size;
    uint32_t sample_count;
    uint32_t first_time_ms;
    uint32_t last_time_ms;
} CampaignReplayFileHeader;

static volatile LONG g_presentation_lock;
static CampaignPresentationSettings g_settings;
static volatile LONG g_settings_loaded;

static CampaignReplaySample* g_replay_samples;
static uint32_t g_replay_capacity;
static uint32_t g_replay_count;
static uint32_t g_replay_write;
static uint32_t g_replay_dropped;
static uint32_t g_replay_active;

static CampaignPhotoState g_photo;

static WCHAR g_settings_path[1024];
static WCHAR g_settings_tmp[1024];
static WCHAR g_settings_bak[1024];

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

static uint32_t HashBytes(const void* p, uint32_t count) {
    const unsigned char* s = (const unsigned char*)p;
    uint32_t h = 2166136261u;
    uint32_t i;
    for (i = 0; i < count; ++i) {
        h ^= s[i];
        h *= 16777619u;
    }
    return h;
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

    if (!ValidateSettings(&candidate)) {
        PresentationUnlock();
        return 0;
    }

    CopyBytes(&g_settings, &candidate, (uint32_t)sizeof(g_settings));
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignPresentationResetSettings(void) {
    PresentationLock();
    InitSettings(&g_settings);
    InterlockedExchange(&g_settings_loaded, 1);
    PresentationUnlock();
    return 1;
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
    g_replay_active = 0;
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
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignReplayRecord(const CampaignReplaySample* sample) {
    if (!sample) return 0;

    PresentationLock();
    if (!g_replay_active || !g_replay_samples || g_replay_capacity == 0) {
        PresentationUnlock();
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

    PresentationUnlock();
    return 1;
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

int __cdecl CampaignReplaySave(const WCHAR* path) {
    HANDLE h;
    DWORD written;
    uint32_t i;
    uint32_t physical;
    CampaignReplayFileHeader header;

    if (!path || !path[0]) return 0;

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
    header.first_time_ms = g_replay_samples[ReplayPhysicalIndexUnlocked(0)].time_ms;
    header.last_time_ms = g_replay_samples[ReplayPhysicalIndexUnlocked(g_replay_count - 1u)].time_ms;

    h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) {
        PresentationUnlock();
        return 0;
    }

    written = 0;
    if (!WriteFile(h, &header, (DWORD)sizeof(header), &written, 0) ||
        written != (DWORD)sizeof(header)) {
        CloseHandle(h);
        DeleteFileW(path);
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
            DeleteFileW(path);
            PresentationUnlock();
            return 0;
        }
    }

    FlushFileBuffers(h);
    CloseHandle(h);
    PresentationUnlock();
    return 1;
}

int __cdecl CampaignPhotoEnter(const CampaignPhotoState* initial) {
    PresentationLock();
    ZeroBytes(&g_photo, (uint32_t)sizeof(g_photo));
    g_photo.size = (uint32_t)sizeof(g_photo);
    g_photo.active = 1;
    g_photo.camera_mode = CAMPAIGN_PHOTO_CAMERA_FREE;
    g_photo.hide_hud = 1;

    if (initial && initial->size >= (uint32_t)sizeof(*initial)) {
        CopyBytes(&g_photo, initial, (uint32_t)sizeof(g_photo));
        g_photo.size = (uint32_t)sizeof(g_photo);
        g_photo.active = 1;
    }

    PresentationUnlock();
    return 1;
}

int __cdecl CampaignPhotoExit(void) {
    PresentationLock();
    ZeroBytes(&g_photo, (uint32_t)sizeof(g_photo));
    g_photo.size = (uint32_t)sizeof(g_photo);
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

    PresentationLock();
    CopyBytes(&g_photo, state, (uint32_t)sizeof(g_photo));
    g_photo.size = (uint32_t)sizeof(g_photo);
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
    default:
        return 0;
    }

    return command->status ? 1 : 0;
}
