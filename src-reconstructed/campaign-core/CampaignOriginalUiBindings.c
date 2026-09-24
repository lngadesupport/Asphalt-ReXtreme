#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignOriginalUiBindings.h"

#define RXIU_MAGIC 0x55495852u /* RXIU */
#define RXIU_VERSION 1u

typedef struct CampaignOriginalUiFileHeader {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t entry_size;
    uint32_t entries_hash;
    uint32_t pe_time_date_stamp;
    uint32_t pe_size_of_image;
} CampaignOriginalUiFileHeader;

static CampaignOriginalUiBinding g_ui_bindings[CAMPAIGN_ORIGINAL_UI_BINDING_MAX];
static CampaignOriginalUiBinding g_ui_load_bindings[CAMPAIGN_ORIGINAL_UI_BINDING_MAX];
static uint32_t g_ui_count;
static volatile LONG g_ui_loaded;
static WCHAR g_ui_path[1024];

static void UiZero(void* p, uint32_t count) {
    volatile unsigned char* q = (volatile unsigned char*)p;
    uint32_t i;
    for (i = 0; i < count; ++i) q[i] = 0;
}

static void UiCopy(void* dst, const void* src, uint32_t count) {
    volatile unsigned char* d = (volatile unsigned char*)dst;
    const volatile unsigned char* s = (const volatile unsigned char*)src;
    uint32_t i;
    for (i = 0; i < count; ++i) d[i] = s[i];
}

static uint32_t UiFnv1a(const unsigned char* data, uint32_t count) {
    uint32_t h = 2166136261u;
    uint32_t i;
    for (i = 0; i < count; ++i) {
        h ^= data[i];
        h *= 16777619u;
    }
    return h;
}

static int UiStringEqual(const char* a, const char* b) {
    uint32_t i = 0;
    if (!a || !b) return 0;
    while (a[i] && b[i]) {
        if (a[i] != b[i]) return 0;
        ++i;
    }
    return a[i] == 0 && b[i] == 0;
}

static int UiIdValid(const char* id) {
    uint32_t i;
    if (!id || !id[0]) return 0;
    for (i = 0; i < CAMPAIGN_ORIGINAL_UI_ID_MAX; ++i) {
        if (id[i] == 0) return 1;
    }
    return 0;
}

static int UiBuildPath(void) {
    DWORD n;
    int i;
    uint32_t pos;
    uint32_t j = 0;
    static const WCHAR suffix[] = L"CampaignOriginalUiBindings.dat";

    UiZero(g_ui_path, (uint32_t)sizeof(g_ui_path));
    n = GetModuleFileNameW(0, g_ui_path, 1024);
    if (n == 0 || n >= 1024) return 0;

    i = (int)n - 1;
    while (i >= 0 && g_ui_path[i] != L'\\' && g_ui_path[i] != L'/') --i;
    if (i < 0) return 0;

    pos = (uint32_t)(i + 1);
    while (suffix[j]) {
        if (pos + 1 >= 1024) return 0;
        g_ui_path[pos++] = suffix[j++];
    }
    g_ui_path[pos] = 0;
    return 1;
}

static int UiExecutableMatches(uint32_t expected_stamp, uint32_t expected_size) {
    unsigned char* module;
    uint32_t pe_off;
    unsigned char* pe;

    module = (unsigned char*)GetModuleHandleW(0);
    if (!module || module[0] != 'M' || module[1] != 'Z') return 0;
    pe_off = *(uint32_t*)(module + 0x3C);
    pe = module + pe_off;
    if (pe[0] != 'P' || pe[1] != 'E' || pe[2] != 0 || pe[3] != 0) return 0;
    if (*(uint16_t*)(pe + 24) != 0x010B) return 0;

    return *(uint32_t*)(pe + 8) == expected_stamp &&
           *(uint32_t*)(pe + 24 + 56) == expected_size;
}

static int UiMemoryReadable(const void* address, SIZE_T size) {
    MEMORY_BASIC_INFORMATION mbi;
    uintptr_t begin, end, region_end;

    if (!address || size == 0) return 0;
    if (VirtualQuery(address, &mbi, sizeof(mbi)) != sizeof(mbi)) return 0;
    if (mbi.State != MEM_COMMIT) return 0;
    if (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS)) return 0;

    begin = (uintptr_t)address;
    end = begin + size;
    if (end < begin) return 0;
    region_end = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;
    return end <= region_end ? 1 : 0;
}

static uint32_t UiCurrentImageSize(void) {
    unsigned char* module;
    uint32_t pe_off;
    unsigned char* pe;

    module = (unsigned char*)GetModuleHandleW(0);
    if (!module || module[0] != 'M' || module[1] != 'Z') return 0;
    pe_off = *(uint32_t*)(module + 0x3C);
    pe = module + pe_off;
    if (pe[0] != 'P' || pe[1] != 'E' || pe[2] != 0 || pe[3] != 0) return 0;
    if (*(uint16_t*)(pe + 24) != 0x010B) return 0;
    return *(uint32_t*)(pe + 24 + 56);
}

static int UiBindingValid(const CampaignOriginalUiBinding* b) {
    if (!b || !UiIdValid(b->id)) return 0;
    if (b->kind < CAMPAIGN_ORIGINAL_UI_SCREEN ||
        b->kind > CAMPAIGN_ORIGINAL_UI_ANIMATION) return 0;
    if (b->base_kind != CAMPAIGN_ORIGINAL_UI_MODULE_RVA &&
        b->base_kind != CAMPAIGN_ORIGINAL_UI_POINTER_RVA) return 0;
    if (b->target_rva == 0) return 0;
    {
        uint32_t image_size = UiCurrentImageSize();
        if (image_size == 0 || b->target_rva >= image_size) return 0;
    }
    return 1;
}

int CampaignOriginalUiBindingsLoad(void) {
    HANDLE h;
    DWORD got = 0;
    CampaignOriginalUiFileHeader header;
    uint32_t i, j;

    UiZero(g_ui_bindings, (uint32_t)sizeof(g_ui_bindings));
    UiZero(g_ui_load_bindings, (uint32_t)sizeof(g_ui_load_bindings));
    g_ui_count = 0;
    InterlockedExchange(&g_ui_loaded, 0);

    if (!UiBuildPath()) return 0;

    h = CreateFileW(
        g_ui_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );

    /* Missing catalog is valid: all ReXtreme-only UI remains hidden. */
    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_ui_loaded, 1);
        return 1;
    }

    UiZero(&header, (uint32_t)sizeof(header));
    if (!ReadFile(h, &header, (DWORD)sizeof(header), &got, 0) ||
        got != (DWORD)sizeof(header) ||
        header.magic != RXIU_MAGIC ||
        header.version != RXIU_VERSION ||
        header.entry_size != (uint32_t)sizeof(CampaignOriginalUiBinding) ||
        header.count > CAMPAIGN_ORIGINAL_UI_BINDING_MAX) {
        CloseHandle(h);
        return 0;
    }

    if (header.count > 0 &&
        !UiExecutableMatches(header.pe_time_date_stamp, header.pe_size_of_image)) {
        CloseHandle(h);
        return 0;
    }

    if (header.count > 0) {
        DWORD bytes = (DWORD)(header.count * (uint32_t)sizeof(CampaignOriginalUiBinding));
        got = 0;
        if (!ReadFile(h, g_ui_load_bindings, bytes, &got, 0) || got != bytes) {
            CloseHandle(h);
            return 0;
        }
        if (header.entries_hash != UiFnv1a((const unsigned char*)g_ui_load_bindings, bytes)) {
            CloseHandle(h);
            return 0;
        }
    } else if (header.entries_hash != UiFnv1a((const unsigned char*)g_ui_load_bindings, 0)) {
        CloseHandle(h);
        return 0;
    }
    CloseHandle(h);

    for (i = 0; i < header.count; ++i) {
        if (!UiBindingValid(&g_ui_load_bindings[i])) return 0;
        for (j = 0; j < i; ++j) {
            if (UiStringEqual(g_ui_load_bindings[i].id, g_ui_load_bindings[j].id)) return 0;
        }
    }

    for (i = 0; i < header.count; ++i) {
        UiCopy(&g_ui_bindings[i], &g_ui_load_bindings[i], (uint32_t)sizeof(g_ui_bindings[i]));
    }
    g_ui_count = header.count;
    InterlockedExchange(&g_ui_loaded, 1);
    return 1;
}

static void UiEnsureLoaded(void) {
    if (InterlockedCompareExchange(&g_ui_loaded, 1, 1) == 0) {
        CampaignOriginalUiBindingsLoad();
    }
}

uint32_t CampaignOriginalUiBindingsCount(void) {
    UiEnsureLoaded();
    return g_ui_count;
}

const CampaignOriginalUiBinding* CampaignOriginalUiBindingsGet(uint32_t index) {
    UiEnsureLoaded();
    if (index >= g_ui_count) return 0;
    return &g_ui_bindings[index];
}

const CampaignOriginalUiBinding* CampaignOriginalUiBindingsFind(const char* id) {
    uint32_t i;
    if (!UiIdValid(id)) return 0;
    UiEnsureLoaded();
    for (i = 0; i < g_ui_count; ++i) {
        if (UiStringEqual(g_ui_bindings[i].id, id)) return &g_ui_bindings[i];
    }
    return 0;
}

void* CampaignOriginalUiBindingsResolve(const char* id) {
    const CampaignOriginalUiBinding* b;
    unsigned char* module;
    unsigned char* base;
    unsigned char* resolved;
    uint32_t image_size;

    b = CampaignOriginalUiBindingsFind(id);
    if (!b) return 0;
    module = (unsigned char*)GetModuleHandleW(0);
    if (!module) return 0;

    image_size = UiCurrentImageSize();
    if (image_size == 0 || b->target_rva >= image_size) return 0;

    if (b->base_kind == CAMPAIGN_ORIGINAL_UI_MODULE_RVA) {
        base = module + b->target_rva;
        if (!UiMemoryReadable(base, 1)) return 0;
    } else {
        void** source = (void**)(module + b->target_rva);
        if (!UiMemoryReadable(source, sizeof(void*))) return 0;
        base = (unsigned char*)*source;
        if (!base || !UiMemoryReadable(base, 1)) return 0;
    }

    resolved = base + b->field_offset;
    if ((b->field_offset > 0 && resolved < base) ||
        (b->field_offset < 0 && resolved > base)) return 0;
    if (!UiMemoryReadable(resolved, 1)) return 0;
    return resolved;
}

static int UiHas(const char* id, uint32_t kind) {
    const CampaignOriginalUiBinding* b = CampaignOriginalUiBindingsFind(id);
    return b && b->kind == kind;
}

int CampaignOriginalUiFeatureReady(uint32_t feature) {
    switch (feature) {
    case CAMPAIGN_ORIGINAL_UI_FEATURE_GRAPHICS_SETTINGS:
        return UiHas("settings.screen", CAMPAIGN_ORIGINAL_UI_SCREEN) &&
               UiHas("settings.row", CAMPAIGN_ORIGINAL_UI_PANEL) &&
               UiHas("ui.slider", CAMPAIGN_ORIGINAL_UI_SLIDER) &&
               UiHas("ui.toggle", CAMPAIGN_ORIGINAL_UI_TOGGLE) &&
               UiHas("ui.button", CAMPAIGN_ORIGINAL_UI_BUTTON) &&
               UiHas("ui.label", CAMPAIGN_ORIGINAL_UI_LABEL);
    case CAMPAIGN_ORIGINAL_UI_FEATURE_CAMERA_SETTINGS:
        return UiHas("settings.screen", CAMPAIGN_ORIGINAL_UI_SCREEN) &&
               UiHas("settings.row", CAMPAIGN_ORIGINAL_UI_PANEL) &&
               UiHas("ui.slider", CAMPAIGN_ORIGINAL_UI_SLIDER) &&
               UiHas("ui.label", CAMPAIGN_ORIGINAL_UI_LABEL);
    case CAMPAIGN_ORIGINAL_UI_FEATURE_REPLAY:
        return UiHas("ui.screen", CAMPAIGN_ORIGINAL_UI_SCREEN) &&
               UiHas("ui.panel", CAMPAIGN_ORIGINAL_UI_PANEL) &&
               UiHas("ui.slider", CAMPAIGN_ORIGINAL_UI_SLIDER) &&
               UiHas("ui.button", CAMPAIGN_ORIGINAL_UI_BUTTON) &&
               UiHas("ui.list", CAMPAIGN_ORIGINAL_UI_LIST) &&
               UiHas("ui.label", CAMPAIGN_ORIGINAL_UI_LABEL);
    case CAMPAIGN_ORIGINAL_UI_FEATURE_PHOTO_MODE:
        return UiHas("pause.screen", CAMPAIGN_ORIGINAL_UI_SCREEN) &&
               UiHas("pause.menu.slot", CAMPAIGN_ORIGINAL_UI_PANEL) &&
               UiHas("ui.panel", CAMPAIGN_ORIGINAL_UI_PANEL) &&
               UiHas("ui.button", CAMPAIGN_ORIGINAL_UI_BUTTON) &&
               UiHas("ui.slider", CAMPAIGN_ORIGINAL_UI_SLIDER) &&
               UiHas("ui.label", CAMPAIGN_ORIGINAL_UI_LABEL);
    case CAMPAIGN_ORIGINAL_UI_FEATURE_RACE_HUD:
        return UiHas("race.hud", CAMPAIGN_ORIGINAL_UI_PANEL) &&
               UiHas("ui.label", CAMPAIGN_ORIGINAL_UI_LABEL);
    case CAMPAIGN_ORIGINAL_UI_FEATURE_CHALLENGES:
        return UiHas("ui.screen", CAMPAIGN_ORIGINAL_UI_SCREEN) &&
               UiHas("ui.panel", CAMPAIGN_ORIGINAL_UI_PANEL) &&
               UiHas("ui.list", CAMPAIGN_ORIGINAL_UI_LIST) &&
               UiHas("ui.tab", CAMPAIGN_ORIGINAL_UI_TAB) &&
               UiHas("ui.button", CAMPAIGN_ORIGINAL_UI_BUTTON) &&
               UiHas("ui.label", CAMPAIGN_ORIGINAL_UI_LABEL);
    case CAMPAIGN_ORIGINAL_UI_FEATURE_ACHIEVEMENTS:
        return UiHas("ui.screen", CAMPAIGN_ORIGINAL_UI_SCREEN) &&
               UiHas("ui.panel", CAMPAIGN_ORIGINAL_UI_PANEL) &&
               UiHas("ui.list", CAMPAIGN_ORIGINAL_UI_LIST) &&
               UiHas("ui.button", CAMPAIGN_ORIGINAL_UI_BUTTON) &&
               UiHas("ui.label", CAMPAIGN_ORIGINAL_UI_LABEL);
    case CAMPAIGN_ORIGINAL_UI_FEATURE_RESULTS:
        return UiHas("results.screen", CAMPAIGN_ORIGINAL_UI_SCREEN) &&
               UiHas("results.row", CAMPAIGN_ORIGINAL_UI_PANEL) &&
               UiHas("ui.label", CAMPAIGN_ORIGINAL_UI_LABEL) &&
               UiHas("ui.button", CAMPAIGN_ORIGINAL_UI_BUTTON);
    case CAMPAIGN_ORIGINAL_UI_FEATURE_PROFILE:
        return UiHas("profile.screen", CAMPAIGN_ORIGINAL_UI_SCREEN) &&
               UiHas("profile.row", CAMPAIGN_ORIGINAL_UI_PANEL) &&
               UiHas("ui.tab", CAMPAIGN_ORIGINAL_UI_TAB) &&
               UiHas("ui.list", CAMPAIGN_ORIGINAL_UI_LIST) &&
               UiHas("ui.label", CAMPAIGN_ORIGINAL_UI_LABEL) &&
               UiHas("ui.button", CAMPAIGN_ORIGINAL_UI_BUTTON);
    case CAMPAIGN_ORIGINAL_UI_FEATURE_SPECIAL_EVENTS:
        return UiHas("special_events.screen", CAMPAIGN_ORIGINAL_UI_SCREEN) &&
               UiHas("special_events.card", CAMPAIGN_ORIGINAL_UI_PANEL) &&
               UiHas("ui.tab", CAMPAIGN_ORIGINAL_UI_TAB) &&
               UiHas("ui.list", CAMPAIGN_ORIGINAL_UI_LIST) &&
               UiHas("ui.label", CAMPAIGN_ORIGINAL_UI_LABEL) &&
               UiHas("ui.button", CAMPAIGN_ORIGINAL_UI_BUTTON);
    case CAMPAIGN_ORIGINAL_UI_FEATURE_CHAMPIONSHIPS:
        return UiHas("ui.screen", CAMPAIGN_ORIGINAL_UI_SCREEN) &&
               UiHas("ui.panel", CAMPAIGN_ORIGINAL_UI_PANEL) &&
               UiHas("ui.list", CAMPAIGN_ORIGINAL_UI_LIST) &&
               UiHas("ui.tab", CAMPAIGN_ORIGINAL_UI_TAB) &&
               UiHas("ui.label", CAMPAIGN_ORIGINAL_UI_LABEL) &&
               UiHas("ui.button", CAMPAIGN_ORIGINAL_UI_BUTTON);
    default:
        return 0;
    }
}
