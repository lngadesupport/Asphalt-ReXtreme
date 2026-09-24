#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignGarageUiTrace.h"

typedef LONG (WINAPI *CampaignGetCurrentPackageFamilyNameFn)(
    UINT32* packageFamilyNameLength,
    PWSTR packageFamilyName
);

#define CAMPAIGN_GARAGE_UI_TRACE_MAGIC 0x49555847u /* GXUI */
#define CAMPAIGN_GS_BASE 0x340u
#define CAMPAIGN_GS_WORDS 32u
#define CAMPAIGN_GBBW_WORDS 40u

typedef struct CampaignGarageUiTraceRecord {
    uint32_t magic;
    uint32_t version;
    uint32_t step;
    uint32_t gs_garage;
    uint32_t widget;
    uint32_t gs_companion;
    uint32_t reserved;
    uint32_t gs_words[CAMPAIGN_GS_WORDS];
    uint32_t widget_words[CAMPAIGN_GBBW_WORDS];
} CampaignGarageUiTraceRecord;

static WCHAR g_local_app_data[1024];
static WCHAR g_family[256];
static WCHAR g_path[1400];

static int BuildTracePath(void) {
    HMODULE kernel32;
    CampaignGetCurrentPackageFamilyNameFn get_family;
    UINT32 family_len = 256;
    DWORD i = 0;
    const WCHAR packages[] = L"\\Packages\\";
    const WCHAR suffix[] =
        L"\\LocalState\\CampaignEdition\\GarageUiTrace.bin";

    kernel32 = GetModuleHandleW(L"kernel32.dll");
    if (!kernel32) return 0;

    get_family = (CampaignGetCurrentPackageFamilyNameFn)
        GetProcAddress(kernel32, "GetCurrentPackageFamilyName");
    if (!get_family) return 0;

    if (!GetEnvironmentVariableW(
            L"LOCALAPPDATA", g_local_app_data, 1024)) return 0;
    if (get_family(&family_len, g_family) != ERROR_SUCCESS) return 0;

    while (g_local_app_data[i] && i < 1399) {
        g_path[i] = g_local_app_data[i];
        ++i;
    }
    if (i >= 1399) return 0;

    {
        DWORD j = 0;
        while (packages[j] && i < 1399) g_path[i++] = packages[j++];
        j = 0;
        while (g_family[j] && i < 1399) g_path[i++] = g_family[j++];
        j = 0;
        while (suffix[j] && i < 1399) g_path[i++] = suffix[j++];
        g_path[i] = 0;
    }
    return 1;
}

static void CopyWords(
    uint32_t* dst,
    volatile const uint32_t* src,
    uint32_t count
) {
    uint32_t i;
    if (!src) {
        for (i = 0; i < count; ++i) dst[i] = 0;
        return;
    }
    for (i = 0; i < count; ++i) dst[i] = src[i];
}

void __cdecl CampaignGarageUiTraceWrite(
    uint32_t step,
    void* gs_garage,
    void* garage_bottom_bar_widget
) {
    CampaignGarageUiTraceRecord r;
    unsigned char* gs = (unsigned char*)gs_garage;
    unsigned char* widget = (unsigned char*)garage_bottom_bar_widget;
    HANDLE file;
    DWORD written;
    uint32_t i;

    for (i = 0; i < (uint32_t)(sizeof(r) / sizeof(uint32_t)); ++i) {
        ((uint32_t*)&r)[i] = 0;
    }

    r.magic = CAMPAIGN_GARAGE_UI_TRACE_MAGIC;
    r.version = 1;
    r.step = step;
    r.gs_garage = (uint32_t)(uintptr_t)gs_garage;
    r.widget = (uint32_t)(uintptr_t)garage_bottom_bar_widget;

    if (gs) {
        r.gs_companion = *(uint32_t*)(gs + 0x360);
        CopyWords(
            r.gs_words,
            (volatile const uint32_t*)(gs + CAMPAIGN_GS_BASE),
            CAMPAIGN_GS_WORDS
        );
    }

    if (widget) {
        CopyWords(
            r.widget_words,
            (volatile const uint32_t*)widget,
            CAMPAIGN_GBBW_WORDS
        );
    }

    if (!BuildTracePath()) return;

    file = CreateFileW(
        g_path,
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        0
    );
    if (file == INVALID_HANDLE_VALUE) return;

    SetFilePointer(file, 0, 0, FILE_END);
    WriteFile(file, &r, (DWORD)sizeof(r), &written, 0);
    CloseHandle(file);
}
