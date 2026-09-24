#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignRaceHudLayout.h"

#define RXHL_MAGIC 0x4C485852u /* RXHL */
#define RXHL_VERSION 1u

typedef struct CampaignRaceHudLayoutFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t entry_size;
    uint32_t entries_hash;
} CampaignRaceHudLayoutFile;

static CampaignRaceHudElementState g_layout[CAMPAIGN_RACE_HUD_LAYOUT_MAX];
static uint32_t g_layout_count;
static volatile LONG g_layout_loaded;
static volatile LONG g_layout_lock;
static WCHAR g_layout_path[1024];
static WCHAR g_layout_tmp[1024];

static void LayoutZero(void* p, uint32_t n) {
    volatile unsigned char* q = (volatile unsigned char*)p;
    uint32_t i;
    for (i = 0; i < n; ++i) q[i] = 0;
}

static void LayoutCopy(void* d0, const void* s0, uint32_t n) {
    volatile unsigned char* d = (volatile unsigned char*)d0;
    const volatile unsigned char* s = (const volatile unsigned char*)s0;
    uint32_t i;
    for (i = 0; i < n; ++i) d[i] = s[i];
}

static uint32_t LayoutHash(const unsigned char* data, uint32_t n) {
    uint32_t h = 2166136261u, i;
    for (i = 0; i < n; ++i) {
        h ^= data[i];
        h *= 16777619u;
    }
    return h;
}

static void LayoutLock(void) {
    while (InterlockedCompareExchange(&g_layout_lock, 1, 0) != 0) Sleep(0);
}

static void LayoutUnlock(void) {
    InterlockedExchange(&g_layout_lock, 0);
}

static int LayoutAppend(WCHAR* dst, uint32_t cap, const WCHAR* src) {
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

static int LayoutEnsureDirectory(const WCHAR* path) {
    DWORD attrs;
    attrs = GetFileAttributesW(path);
    if (attrs != INVALID_FILE_ATTRIBUTES) return (attrs & FILE_ATTRIBUTE_DIRECTORY) ? 1 : 0;
    if (CreateDirectoryW(path, 0)) return 1;
    return GetLastError() == ERROR_ALREADY_EXISTS ? 1 : 0;
}

static int LayoutBuildPaths(void) {
    WCHAR exe[1024];
    DWORD n;
    int i;

    if (g_layout_path[0]) return 1;
    LayoutZero(exe, (uint32_t)sizeof(exe));
    n = GetModuleFileNameW(0, exe, 1024);
    if (n == 0 || n >= 1024) return 0;
    i = (int)n - 1;
    while (i >= 0 && exe[i] != L'\\' && exe[i] != L'/') --i;
    if (i < 0) return 0;
    exe[i + 1] = 0;

    LayoutZero(g_layout_path, (uint32_t)sizeof(g_layout_path));
    LayoutZero(g_layout_tmp, (uint32_t)sizeof(g_layout_tmp));

    if (!LayoutAppend(g_layout_path, 1024, exe)) return 0;
    if (!LayoutAppend(g_layout_path, 1024, L"UserData")) return 0;
    if (!LayoutEnsureDirectory(g_layout_path)) return 0;
    if (!LayoutAppend(g_layout_path, 1024, L"\\RaceHudLayout.dat")) return 0;

    if (!LayoutAppend(g_layout_tmp, 1024, exe)) return 0;
    if (!LayoutAppend(g_layout_tmp, 1024, L"UserData")) return 0;
    if (!LayoutAppend(g_layout_tmp, 1024, L"\\RaceHudLayout.tmp")) return 0;
    return 1;
}

static int LayoutStateValid(const CampaignRaceHudElementState* s) {
    uint32_t known =
        CAMPAIGN_RACE_HUD_SET_X |
        CAMPAIGN_RACE_HUD_SET_Y |
        CAMPAIGN_RACE_HUD_SET_SCALE |
        CAMPAIGN_RACE_HUD_SET_OPACITY |
        CAMPAIGN_RACE_HUD_SET_VISIBLE;

    if (!s || s->size != (uint32_t)sizeof(*s)) return 0;
    if (s->element < CAMPAIGN_RACE_HUD_POSITION ||
        s->element > CAMPAIGN_RACE_HUD_OBJECTIVE) return 0;
    if (s->set_flags == 0 || (s->set_flags & ~known)) return 0;
    if ((s->set_flags & CAMPAIGN_RACE_HUD_SET_SCALE) && s->scale_x1000 <= 0) return 0;
    if ((s->set_flags & CAMPAIGN_RACE_HUD_SET_OPACITY) &&
        (s->opacity_x1000 < 0 || s->opacity_x1000 > 1000)) return 0;
    if ((s->set_flags & CAMPAIGN_RACE_HUD_SET_VISIBLE) &&
        s->visible != 0 && s->visible != 1) return 0;
    return 1;
}

static int LayoutWriteAtomicUnlocked(void) {
    CampaignRaceHudLayoutFile header;
    HANDLE h;
    DWORD written = 0;
    DWORD bytes;

    if (!LayoutBuildPaths()) return 0;
    LayoutZero(&header, (uint32_t)sizeof(header));
    header.magic = RXHL_MAGIC;
    header.version = RXHL_VERSION;
    header.count = g_layout_count;
    header.entry_size = (uint32_t)sizeof(CampaignRaceHudElementState);
    bytes = g_layout_count * (DWORD)sizeof(CampaignRaceHudElementState);
    header.entries_hash = LayoutHash((const unsigned char*)g_layout, bytes);

    DeleteFileW(g_layout_tmp);
    h = CreateFileW(g_layout_tmp, GENERIC_WRITE, FILE_SHARE_READ, 0,
                    CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;

    if (!WriteFile(h, &header, (DWORD)sizeof(header), &written, 0) ||
        written != (DWORD)sizeof(header)) {
        CloseHandle(h);
        DeleteFileW(g_layout_tmp);
        return 0;
    }

    if (bytes > 0) {
        written = 0;
        if (!WriteFile(h, g_layout, bytes, &written, 0) || written != bytes) {
            CloseHandle(h);
            DeleteFileW(g_layout_tmp);
            return 0;
        }
    }

    FlushFileBuffers(h);
    CloseHandle(h);
    if (!MoveFileExW(g_layout_tmp, g_layout_path,
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(g_layout_tmp);
        return 0;
    }
    return 1;
}

int CampaignRaceHudLayoutLoad(void) {
    CampaignRaceHudLayoutFile header;
    CampaignRaceHudElementState temp[CAMPAIGN_RACE_HUD_LAYOUT_MAX];
    HANDLE h;
    DWORD got = 0;
    DWORD bytes;
    uint32_t i, j;

    LayoutLock();
    LayoutZero(g_layout, (uint32_t)sizeof(g_layout));
    g_layout_count = 0;
    InterlockedExchange(&g_layout_loaded, 0);

    if (!LayoutBuildPaths()) {
        LayoutUnlock();
        return 0;
    }

    h = CreateFileW(g_layout_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                    0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_layout_loaded, 1);
        LayoutUnlock();
        return 1;
    }

    LayoutZero(&header, (uint32_t)sizeof(header));
    LayoutZero(temp, (uint32_t)sizeof(temp));
    if (!ReadFile(h, &header, (DWORD)sizeof(header), &got, 0) ||
        got != (DWORD)sizeof(header) ||
        header.magic != RXHL_MAGIC ||
        header.version != RXHL_VERSION ||
        header.entry_size != (uint32_t)sizeof(CampaignRaceHudElementState) ||
        header.count > CAMPAIGN_RACE_HUD_LAYOUT_MAX) {
        CloseHandle(h);
        LayoutUnlock();
        return 0;
    }

    bytes = header.count * (DWORD)sizeof(CampaignRaceHudElementState);
    if (bytes > 0) {
        got = 0;
        if (!ReadFile(h, temp, bytes, &got, 0) || got != bytes ||
            header.entries_hash != LayoutHash((const unsigned char*)temp, bytes)) {
            CloseHandle(h);
            LayoutUnlock();
            return 0;
        }
    } else if (header.entries_hash != LayoutHash((const unsigned char*)temp, 0)) {
        CloseHandle(h);
        LayoutUnlock();
        return 0;
    }
    CloseHandle(h);

    for (i = 0; i < header.count; ++i) {
        if (!LayoutStateValid(&temp[i])) {
            LayoutUnlock();
            return 0;
        }
        for (j = 0; j < i; ++j) {
            if (temp[i].element == temp[j].element) {
                LayoutUnlock();
                return 0;
            }
        }
    }

    for (i = 0; i < header.count; ++i) {
        LayoutCopy(&g_layout[i], &temp[i], (uint32_t)sizeof(g_layout[i]));
    }
    g_layout_count = header.count;
    InterlockedExchange(&g_layout_loaded, 1);
    LayoutUnlock();
    return 1;
}

static void LayoutEnsureLoaded(void) {
    if (InterlockedCompareExchange(&g_layout_loaded, 1, 1) == 0) {
        CampaignRaceHudLayoutLoad();
    }
}

int CampaignRaceHudLayoutSave(void) {
    int result;
    LayoutEnsureLoaded();
    LayoutLock();
    result = LayoutWriteAtomicUnlocked();
    LayoutUnlock();
    return result;
}

int CampaignRaceHudLayoutReset(void) {
    int result;
    LayoutLock();
    LayoutZero(g_layout, (uint32_t)sizeof(g_layout));
    g_layout_count = 0;
    InterlockedExchange(&g_layout_loaded, 1);
    if (!LayoutBuildPaths()) {
        LayoutUnlock();
        return 0;
    }
    result = DeleteFileW(g_layout_path) || GetLastError() == ERROR_FILE_NOT_FOUND;
    DeleteFileW(g_layout_tmp);
    LayoutUnlock();
    return result ? 1 : 0;
}

uint32_t CampaignRaceHudLayoutCount(void) {
    LayoutEnsureLoaded();
    return g_layout_count;
}

int CampaignRaceHudLayoutGet(uint32_t index, CampaignRaceHudElementState* out) {
    if (!out || out->size < (uint32_t)sizeof(*out)) return 0;
    LayoutEnsureLoaded();
    LayoutLock();
    if (index >= g_layout_count) {
        LayoutUnlock();
        return 0;
    }
    LayoutCopy(out, &g_layout[index], (uint32_t)sizeof(*out));
    LayoutUnlock();
    return 1;
}

int CampaignRaceHudLayoutSet(const CampaignRaceHudElementState* state) {
    uint32_t i;
    if (!LayoutStateValid(state)) return 0;
    LayoutEnsureLoaded();
    LayoutLock();

    for (i = 0; i < g_layout_count; ++i) {
        if (g_layout[i].element == state->element) {
            LayoutCopy(&g_layout[i], state, (uint32_t)sizeof(*state));
            LayoutUnlock();
            return 1;
        }
    }

    if (g_layout_count >= CAMPAIGN_RACE_HUD_LAYOUT_MAX) {
        LayoutUnlock();
        return 0;
    }
    LayoutCopy(&g_layout[g_layout_count++], state, (uint32_t)sizeof(*state));
    LayoutUnlock();
    return 1;
}

int CampaignRaceHudLayoutApply(void) {
    uint32_t i;
    LayoutEnsureLoaded();
    LayoutLock();
    for (i = 0; i < g_layout_count; ++i) {
        if (!CampaignRaceHudApplyElement(&g_layout[i])) {
            LayoutUnlock();
            return 0;
        }
    }
    LayoutUnlock();
    return 1;
}
