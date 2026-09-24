#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignPresentationCatalog.h"

#define RXPC_MAGIC 0x43505852u /* RXPC */
#define RXPC_VERSION 1u

typedef struct CampaignPresentationCatalogHeader {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t entry_size;
} CampaignPresentationCatalogHeader;

static CampaignPresentationCapability g_entries[CAMPAIGN_PRESENTATION_CAPABILITY_MAX];
static CampaignPresentationCapability g_load_entries[CAMPAIGN_PRESENTATION_CAPABILITY_MAX];
static uint32_t g_count;
static volatile LONG g_loaded;

static void ZeroBytes(void* p, uint32_t count) {
    volatile unsigned char* q = (volatile unsigned char*)p;
    uint32_t i;
    for (i = 0; i < count; ++i) q[i] = 0;
}

static int StringEqual(const char* a, const char* b) {
    uint32_t i = 0;
    if (!a || !b) return 0;
    while (a[i] && b[i]) {
        if (a[i] != b[i]) return 0;
        ++i;
    }
    return a[i] == 0 && b[i] == 0;
}

static int BuildCatalogPath(WCHAR* out, uint32_t cap) {
    DWORD n;
    int i;

    if (!out || cap < 64) return 0;
    ZeroBytes(out, cap * (uint32_t)sizeof(WCHAR));

    n = GetModuleFileNameW(0, out, cap);
    if (n == 0 || n >= cap) return 0;

    i = (int)n - 1;
    while (i >= 0 && out[i] != L'\\' && out[i] != L'/') --i;
    if (i < 0) return 0;
    out[i + 1] = 0;

    {
        static const WCHAR suffix[] = L"CampaignPresentationOptions.dat";
        uint32_t pos = (uint32_t)(i + 1);
        uint32_t j = 0;
        while (suffix[j]) {
            if (pos + 1 >= cap) return 0;
            out[pos++] = suffix[j++];
        }
        out[pos] = 0;
    }
    return 1;
}

static int ValidateEntry(const CampaignPresentationCapability* entry) {
    uint32_t i;
    int terminated = 0;

    if (!entry) return 0;
    for (i = 0; i < CAMPAIGN_PRESENTATION_CAPABILITY_ID_MAX; ++i) {
        if (entry->id[i] == 0) {
            terminated = 1;
            break;
        }
    }
    if (!terminated || entry->id[0] == 0) return 0;
    if (!(entry->flags & CAMPAIGN_PRESENTATION_CAPABILITY_VERIFIED)) return 0;

    if (entry->kind != CAMPAIGN_PRESENTATION_CAPABILITY_TOGGLE &&
        entry->kind != CAMPAIGN_PRESENTATION_CAPABILITY_CHOICE &&
        entry->kind != CAMPAIGN_PRESENTATION_CAPABILITY_SLIDER) {
        return 0;
    }

    if (entry->minimum > entry->maximum) return 0;
    if (entry->step < 0) return 0;
    if (entry->original_value < entry->minimum || entry->original_value > entry->maximum) return 0;
    return 1;
}

int CampaignPresentationCatalogLoad(void) {
    WCHAR path[1024];
    HANDLE h;
    DWORD got;
    CampaignPresentationCatalogHeader header;
    CampaignPresentationCapability* temp = g_load_entries;
    uint32_t i;

    ZeroBytes(g_entries, (uint32_t)sizeof(g_entries));
    g_count = 0;
    InterlockedExchange(&g_loaded, 0);

    if (!BuildCatalogPath(path, 1024)) return 0;

    h = CreateFileW(
        path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );

    /*
      Missing catalog is valid and means "show no extra settings".
      This is the safe default until capabilities are verified.
    */
    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_loaded, 1);
        return 1;
    }

    ZeroBytes(&header, (uint32_t)sizeof(header));
    got = 0;
    if (!ReadFile(h, &header, (DWORD)sizeof(header), &got, 0) ||
        got != (DWORD)sizeof(header) ||
        header.magic != RXPC_MAGIC ||
        header.version != RXPC_VERSION ||
        header.entry_size != (uint32_t)sizeof(CampaignPresentationCapability) ||
        header.count > CAMPAIGN_PRESENTATION_CAPABILITY_MAX) {
        CloseHandle(h);
        return 0;
    }

    ZeroBytes(temp, (uint32_t)sizeof(temp));
    if (header.count > 0) {
        DWORD bytes = (DWORD)(header.count * (uint32_t)sizeof(CampaignPresentationCapability));
        got = 0;
        if (!ReadFile(h, temp, bytes, &got, 0) || got != bytes) {
            CloseHandle(h);
            return 0;
        }
    }
    CloseHandle(h);

    for (i = 0; i < header.count; ++i) {
        if (!ValidateEntry(&temp[i])) return 0;
        {
            uint32_t j;
            for (j = 0; j < i; ++j) {
                if (StringEqual(temp[i].id, temp[j].id)) return 0;
            }
        }
    }

    for (i = 0; i < header.count; ++i) g_entries[i] = temp[i];
    g_count = header.count;
    InterlockedExchange(&g_loaded, 1);
    return 1;
}

static void EnsureLoaded(void) {
    if (InterlockedCompareExchange(&g_loaded, 1, 1) == 0) {
        CampaignPresentationCatalogLoad();
    }
}

uint32_t CampaignPresentationCatalogCount(void) {
    EnsureLoaded();
    return g_count;
}

const CampaignPresentationCapability* CampaignPresentationCatalogGet(uint32_t index) {
    EnsureLoaded();
    if (index >= g_count) return 0;
    return &g_entries[index];
}

const CampaignPresentationCapability* CampaignPresentationCatalogFind(const char* id) {
    uint32_t i;
    if (!id || !id[0]) return 0;
    EnsureLoaded();
    for (i = 0; i < g_count; ++i) {
        if (StringEqual(g_entries[i].id, id)) return &g_entries[i];
    }
    return 0;
}
