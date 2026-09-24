#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignPresentationCatalog.h"
#include "CampaignPresentationBindings.h"

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
static WCHAR g_options_ini_path[1024];

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

static int AsciiToWide(const char* src, WCHAR* dst, uint32_t cap) {
    uint32_t i = 0;
    if (!src || !dst || cap == 0) return 0;
    while (src[i]) {
        unsigned char ch = (unsigned char)src[i];
        if (ch > 0x7F || i + 1 >= cap) return 0;
        dst[i] = (WCHAR)ch;
        ++i;
    }
    dst[i] = 0;
    return 1;
}

static int IntToWide(int32_t value, WCHAR* dst, uint32_t cap) {
    WCHAR temp[32];
    uint32_t count = 0;
    uint32_t out = 0;
    uint32_t magnitude;
    int negative = value < 0;

    if (!dst || cap < 2) return 0;

    if (negative) {
        magnitude = (uint32_t)(-(value + 1));
        ++magnitude;
    } else {
        magnitude = (uint32_t)value;
    }

    do {
        if (count >= 31) return 0;
        temp[count++] = (WCHAR)(L'0' + (magnitude % 10u));
        magnitude /= 10u;
    } while (magnitude != 0);

    if (negative) {
        if (out + 1 >= cap) return 0;
        dst[out++] = L'-';
    }

    while (count > 0) {
        if (out + 1 >= cap) return 0;
        dst[out++] = temp[--count];
    }
    dst[out] = 0;
    return 1;
}

static int BuildOptionsIniPath(void) {
    DWORD n;
    int i;

    if (g_options_ini_path[0]) return 1;
    ZeroBytes(g_options_ini_path, (uint32_t)sizeof(g_options_ini_path));

    n = GetModuleFileNameW(0, g_options_ini_path, 1024);
    if (n == 0 || n >= 1024) return 0;

    i = (int)n - 1;
    while (i >= 0 && g_options_ini_path[i] != L'\\' && g_options_ini_path[i] != L'/') --i;
    if (i < 0) return 0;
    g_options_ini_path[i + 1] = 0;

    {
        static const WCHAR suffix[] = L"ReXtreme.ini";
        uint32_t pos = (uint32_t)(i + 1);
        uint32_t j = 0;
        while (suffix[j]) {
            if (pos + 1 >= 1024) return 0;
            g_options_ini_path[pos++] = suffix[j++];
        }
        g_options_ini_path[pos] = 0;
    }
    return 1;
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

uint32_t CampaignPresentationCatalogRuntimeReadyCount(void) {
    uint32_t i;
    uint32_t count = 0;
    EnsureLoaded();
    for (i = 0; i < g_count; ++i) {
        if (CampaignPresentationBindingsFind(g_entries[i].id)) ++count;
    }
    return count;
}

int CampaignPresentationCapabilityRuntimeReady(uint32_t index) {
    const CampaignPresentationCapability* capability;
    capability = CampaignPresentationCatalogGet(index);
    if (!capability) return 0;
    if (!(capability->flags & CAMPAIGN_PRESENTATION_CAPABILITY_VERIFIED)) return 0;
    return CampaignPresentationBindingsFind(capability->id) ? 1 : 0;
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

int CampaignPresentationCapabilityValueValid(
    const CampaignPresentationCapability* capability,
    int32_t value
) {
    int32_t delta;

    if (!capability) return 0;
    if (!(capability->flags & CAMPAIGN_PRESENTATION_CAPABILITY_VERIFIED)) return 0;
    if (value < capability->minimum || value > capability->maximum) return 0;

    if (capability->step > 0) {
        delta = value - capability->minimum;
        if ((delta % capability->step) != 0) return 0;
    }
    return 1;
}

int CampaignPresentationCatalogGetValue(uint32_t index, int32_t* out_value) {
    const CampaignPresentationCapability* capability;
    WCHAR key[CAMPAIGN_PRESENTATION_CAPABILITY_ID_MAX];
    int value;

    if (!out_value) return 0;
    capability = CampaignPresentationCatalogGet(index);
    if (!capability) return 0;
    if (!BuildOptionsIniPath()) return 0;
    if (!AsciiToWide(capability->id, key, CAMPAIGN_PRESENTATION_CAPABILITY_ID_MAX)) return 0;

    value = GetPrivateProfileIntW(
        L"VerifiedPresentation",
        key,
        capability->original_value,
        g_options_ini_path
    );

    if (!CampaignPresentationCapabilityValueValid(capability, value)) {
        value = capability->original_value;
    }

    *out_value = value;
    return 1;
}

int CampaignPresentationCatalogSetValue(uint32_t index, int32_t value) {
    const CampaignPresentationCapability* capability;
    WCHAR key[CAMPAIGN_PRESENTATION_CAPABILITY_ID_MAX];
    WCHAR text[32];

    capability = CampaignPresentationCatalogGet(index);
    if (!capability) return 0;
    if (!CampaignPresentationCapabilityValueValid(capability, value)) return 0;
    if (!CampaignPresentationBindingsApply(capability->id, value)) return 0;
    if (!BuildOptionsIniPath()) return 0;
    if (!AsciiToWide(capability->id, key, CAMPAIGN_PRESENTATION_CAPABILITY_ID_MAX)) return 0;
    if (!IntToWide(value, text, 32)) return 0;

    return WritePrivateProfileStringW(
        L"VerifiedPresentation",
        key,
        text,
        g_options_ini_path
    ) ? 1 : 0;
}

int CampaignPresentationCatalogResetValue(uint32_t index) {
    const CampaignPresentationCapability* capability;
    WCHAR key[CAMPAIGN_PRESENTATION_CAPABILITY_ID_MAX];

    capability = CampaignPresentationCatalogGet(index);
    if (!capability) return 0;
    if (!CampaignPresentationBindingsApply(
            capability->id,
            capability->original_value)) {
        return 0;
    }
    if (!BuildOptionsIniPath()) return 0;
    if (!AsciiToWide(capability->id, key, CAMPAIGN_PRESENTATION_CAPABILITY_ID_MAX)) return 0;

    return WritePrivateProfileStringW(
        L"VerifiedPresentation",
        key,
        0,
        g_options_ini_path
    ) ? 1 : 0;
}
