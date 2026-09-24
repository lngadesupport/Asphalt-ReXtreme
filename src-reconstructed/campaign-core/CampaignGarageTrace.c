#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignGarageTrace.h"

typedef LONG (WINAPI *CampaignGetCurrentPackageFamilyNameFn)(
    UINT32* packageFamilyNameLength,
    PWSTR packageFamilyName
);

typedef struct CampaignGarageTraceRecord {
    uint32_t magic;
    uint32_t version;
    uint32_t step;
    uint32_t gs_garage;
    uint32_t holder;
    uint32_t selected;
    int32_t car_id;
    int32_t acquire_ok;
    int32_t owned;
    int32_t callback_status;
    uint32_t revision;
} CampaignGarageTraceRecord;

#define CAMPAIGN_GARAGE_TRACE_MAGIC 0x47545852u

static WCHAR g_local_app_data[1024];
static WCHAR g_family[256];
static WCHAR g_path[1400];

void __cdecl CampaignGarageTraceWrite(
    uint32_t step,
    void* gs_garage,
    void* holder,
    void* selected,
    int32_t car_id,
    int32_t acquire_ok,
    int32_t owned,
    int32_t callback_status,
    uint32_t revision
) {
    HMODULE kernel32;
    CampaignGetCurrentPackageFamilyNameFn get_family;
    UINT32 family_len = 256;
    HANDLE file;
    DWORD written;
    DWORD i;
    CampaignGarageTraceRecord r;
    const WCHAR packages[] = L"\\Packages\\";
    const WCHAR suffix[] =
        L"\\LocalState\\CampaignEdition\\GarageTrace.bin";

    kernel32 = GetModuleHandleW(L"kernel32.dll");
    if (!kernel32) return;

    get_family = (CampaignGetCurrentPackageFamilyNameFn)
        GetProcAddress(kernel32, "GetCurrentPackageFamilyName");
    if (!get_family) return;

    if (!GetEnvironmentVariableW(L"LOCALAPPDATA", g_local_app_data, 1024)) {
        return;
    }
    if (get_family(&family_len, g_family) != ERROR_SUCCESS) return;

    i = 0;
    while (g_local_app_data[i] && i < 1399) {
        g_path[i] = g_local_app_data[i];
        ++i;
    }
    if (i >= 1399) return;

    {
        DWORD j = 0;
        while (packages[j] && i < 1399) g_path[i++] = packages[j++];
        j = 0;
        while (g_family[j] && i < 1399) g_path[i++] = g_family[j++];
        j = 0;
        while (suffix[j] && i < 1399) g_path[i++] = suffix[j++];
        g_path[i] = 0;
    }

    r.magic = CAMPAIGN_GARAGE_TRACE_MAGIC;
    r.version = 1;
    r.step = step;
    r.gs_garage = (uint32_t)(uintptr_t)gs_garage;
    r.holder = (uint32_t)(uintptr_t)holder;
    r.selected = (uint32_t)(uintptr_t)selected;
    r.car_id = car_id;
    r.acquire_ok = acquire_ok;
    r.owned = owned;
    r.callback_status = callback_status;
    r.revision = revision;

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
