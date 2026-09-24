#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignRaceHudBindings.h"
#include "CampaignOriginalUiBindings.h"

#define RXHB_MAGIC 0x42485852u /* RXHB */
#define RXHB_VERSION 1u
#define RXHB_VERIFIED 1u

typedef struct CampaignRaceHudFileHeader {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t entry_size;
    uint32_t entries_hash;
    uint32_t pe_time_date_stamp;
    uint32_t pe_size_of_image;
} CampaignRaceHudFileHeader;

static CampaignRaceHudBinding g_hud_bindings[CAMPAIGN_RACE_HUD_BINDING_MAX];
static CampaignRaceHudBinding g_hud_load[CAMPAIGN_RACE_HUD_BINDING_MAX];
static uint32_t g_hud_count;
static volatile LONG g_hud_loaded;
static WCHAR g_hud_path[1024];

static void HudZero(void* p, uint32_t n) {
    volatile unsigned char* q = (volatile unsigned char*)p;
    uint32_t i;
    for (i = 0; i < n; ++i) q[i] = 0;
}

static void HudCopy(void* d0, const void* s0, uint32_t n) {
    volatile unsigned char* d = (volatile unsigned char*)d0;
    const volatile unsigned char* s = (const volatile unsigned char*)s0;
    uint32_t i;
    for (i = 0; i < n; ++i) d[i] = s[i];
}

static uint32_t HudHash(const unsigned char* data, uint32_t count) {
    uint32_t h = 2166136261u, i;
    for (i = 0; i < count; ++i) {
        h ^= data[i];
        h *= 16777619u;
    }
    return h;
}

static int HudMemoryWritable(void* address, SIZE_T size) {
    MEMORY_BASIC_INFORMATION mbi;
    uintptr_t begin, end, region_end;
    DWORD p;

    if (!address || size == 0) return 0;
    if (VirtualQuery(address, &mbi, sizeof(mbi)) != sizeof(mbi)) return 0;
    if (mbi.State != MEM_COMMIT || (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS))) return 0;

    p = mbi.Protect & 0xFFu;
    if (p != PAGE_READWRITE &&
        p != PAGE_WRITECOPY &&
        p != PAGE_EXECUTE_READWRITE &&
        p != PAGE_EXECUTE_WRITECOPY) return 0;

    begin = (uintptr_t)address;
    end = begin + size;
    if (end < begin) return 0;
    region_end = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;
    return end <= region_end ? 1 : 0;
}

static int HudBuildPath(void) {
    DWORD n;
    int i;
    uint32_t pos, j = 0;
    static const WCHAR suffix[] = L"CampaignRaceHudBindings.dat";

    HudZero(g_hud_path, (uint32_t)sizeof(g_hud_path));
    n = GetModuleFileNameW(0, g_hud_path, 1024);
    if (n == 0 || n >= 1024) return 0;
    i = (int)n - 1;
    while (i >= 0 && g_hud_path[i] != L'\\' && g_hud_path[i] != L'/') --i;
    if (i < 0) return 0;
    pos = (uint32_t)(i + 1);
    while (suffix[j]) {
        if (pos + 1 >= 1024) return 0;
        g_hud_path[pos++] = suffix[j++];
    }
    g_hud_path[pos] = 0;
    return 1;
}

static int HudExecutableMatches(uint32_t stamp, uint32_t size_of_image) {
    unsigned char* module = (unsigned char*)GetModuleHandleW(0);
    uint32_t pe_off;
    unsigned char* pe;
    if (!module || module[0] != 'M' || module[1] != 'Z') return 0;
    pe_off = *(uint32_t*)(module + 0x3C);
    pe = module + pe_off;
    if (pe[0] != 'P' || pe[1] != 'E' || pe[2] != 0 || pe[3] != 0) return 0;
    if (*(uint16_t*)(pe + 24) != 0x010B) return 0;
    return *(uint32_t*)(pe + 8) == stamp &&
           *(uint32_t*)(pe + 24 + 56) == size_of_image;
}

static uint32_t HudImageSize(void) {
    unsigned char* module = (unsigned char*)GetModuleHandleW(0);
    uint32_t pe_off;
    unsigned char* pe;
    if (!module || module[0] != 'M' || module[1] != 'Z') return 0;
    pe_off = *(uint32_t*)(module + 0x3C);
    pe = module + pe_off;
    if (pe[0] != 'P' || pe[1] != 'E' || pe[2] != 0 || pe[3] != 0) return 0;
    if (*(uint16_t*)(pe + 24) != 0x010B) return 0;
    return *(uint32_t*)(pe + 24 + 56);
}

static int HudElementValid(uint32_t element) {
    return element >= CAMPAIGN_RACE_HUD_POSITION &&
           element <= CAMPAIGN_RACE_HUD_OBJECTIVE;
}

static int HudPropertyValid(uint32_t property) {
    return property >= CAMPAIGN_RACE_HUD_PROP_X &&
           property <= CAMPAIGN_RACE_HUD_PROP_VISIBLE;
}

static int HudBindingValid(const CampaignRaceHudBinding* b) {
    uint32_t image_size;
    if (!b || !HudElementValid(b->element) || !HudPropertyValid(b->property)) return 0;
    if (!(b->flags & RXHB_VERIFIED)) return 0;
    if (b->base_kind != CAMPAIGN_PRESENTATION_BASE_MODULE_RVA &&
        b->base_kind != CAMPAIGN_PRESENTATION_BASE_POINTER_RVA &&
        b->base_kind != CAMPAIGN_RACE_HUD_BASE_GUI_ARGUMENT) return 0;
    image_size = HudImageSize();
    if (image_size == 0) return 0;
    if (b->base_kind == CAMPAIGN_RACE_HUD_BASE_GUI_ARGUMENT) {
        if (b->target_rva != 0) return 0;
    } else if (b->target_rva == 0 || b->target_rva >= image_size) {
        return 0;
    }
    if (b->value_kind != CAMPAIGN_PRESENTATION_VALUE_I32 &&
        b->value_kind != CAMPAIGN_PRESENTATION_VALUE_U32 &&
        b->value_kind != CAMPAIGN_PRESENTATION_VALUE_U8_BOOL &&
        b->value_kind != CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED) return 0;
    if (b->value_kind == CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED) {
        if (b->scale_divisor <= 0) return 0;
    } else if (b->scale_divisor != 1) return 0;
    return 1;
}

int CampaignRaceHudBindingsLoad(void) {
    HANDLE h;
    DWORD got = 0;
    CampaignRaceHudFileHeader header;
    uint32_t i, j;

    HudZero(g_hud_bindings, (uint32_t)sizeof(g_hud_bindings));
    HudZero(g_hud_load, (uint32_t)sizeof(g_hud_load));
    g_hud_count = 0;
    InterlockedExchange(&g_hud_loaded, 0);
    if (!HudBuildPath()) return 0;

    h = CreateFileW(g_hud_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0,
                    OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_hud_loaded, 1);
        return 1;
    }

    HudZero(&header, (uint32_t)sizeof(header));
    if (!ReadFile(h, &header, (DWORD)sizeof(header), &got, 0) ||
        got != (DWORD)sizeof(header) ||
        header.magic != RXHB_MAGIC ||
        header.version != RXHB_VERSION ||
        header.entry_size != (uint32_t)sizeof(CampaignRaceHudBinding) ||
        header.count > CAMPAIGN_RACE_HUD_BINDING_MAX) {
        CloseHandle(h);
        return 0;
    }

    if (header.count > 0 &&
        !HudExecutableMatches(header.pe_time_date_stamp, header.pe_size_of_image)) {
        CloseHandle(h);
        return 0;
    }

    if (header.count > 0) {
        DWORD bytes = (DWORD)(header.count * (uint32_t)sizeof(CampaignRaceHudBinding));
        got = 0;
        if (!ReadFile(h, g_hud_load, bytes, &got, 0) || got != bytes) {
            CloseHandle(h);
            return 0;
        }
        if (header.entries_hash != HudHash((const unsigned char*)g_hud_load, bytes)) {
            CloseHandle(h);
            return 0;
        }
    } else if (header.entries_hash != HudHash((const unsigned char*)g_hud_load, 0)) {
        CloseHandle(h);
        return 0;
    }
    CloseHandle(h);

    for (i = 0; i < header.count; ++i) {
        if (!HudBindingValid(&g_hud_load[i])) return 0;
        for (j = 0; j < i; ++j) {
            if (g_hud_load[i].element == g_hud_load[j].element &&
                g_hud_load[i].property == g_hud_load[j].property) return 0;
        }
    }

    for (i = 0; i < header.count; ++i) {
        HudCopy(&g_hud_bindings[i], &g_hud_load[i], (uint32_t)sizeof(g_hud_bindings[i]));
    }
    g_hud_count = header.count;
    InterlockedExchange(&g_hud_loaded, 1);
    return 1;
}

static void HudEnsureLoaded(void) {
    if (InterlockedCompareExchange(&g_hud_loaded, 1, 1) == 0) CampaignRaceHudBindingsLoad();
}

uint32_t CampaignRaceHudBindingsCount(void) {
    HudEnsureLoaded();
    return g_hud_count;
}

const CampaignRaceHudBinding* CampaignRaceHudBindingsFind(uint32_t element, uint32_t property) {
    uint32_t i;
    HudEnsureLoaded();
    for (i = 0; i < g_hud_count; ++i) {
        if (g_hud_bindings[i].element == element &&
            g_hud_bindings[i].property == property) return &g_hud_bindings[i];
    }
    return 0;
}

static uint32_t HudFlagForProperty(uint32_t property) {
    switch (property) {
    case CAMPAIGN_RACE_HUD_PROP_X: return CAMPAIGN_RACE_HUD_SET_X;
    case CAMPAIGN_RACE_HUD_PROP_Y: return CAMPAIGN_RACE_HUD_SET_Y;
    case CAMPAIGN_RACE_HUD_PROP_SCALE: return CAMPAIGN_RACE_HUD_SET_SCALE;
    case CAMPAIGN_RACE_HUD_PROP_OPACITY: return CAMPAIGN_RACE_HUD_SET_OPACITY;
    case CAMPAIGN_RACE_HUD_PROP_VISIBLE: return CAMPAIGN_RACE_HUD_SET_VISIBLE;
    default: return 0;
    }
}

int CampaignRaceHudElementReady(uint32_t element, uint32_t property_mask) {
    uint32_t property;
    if (!HudElementValid(element)) return 0;
    for (property = CAMPAIGN_RACE_HUD_PROP_X;
         property <= CAMPAIGN_RACE_HUD_PROP_VISIBLE;
         ++property) {
        uint32_t flag = HudFlagForProperty(property);
        if ((property_mask & flag) && !CampaignRaceHudBindingsFind(element, property)) return 0;
    }
    return 1;
}

static void* HudResolve(
    const CampaignRaceHudBinding* b,
    SIZE_T size,
    void* game_mode_gui
) {
    unsigned char* module;
    unsigned char* base;
    unsigned char* target;
    uint32_t image_size;

    if (!b) return 0;
    module = (unsigned char*)GetModuleHandleW(0);
    if (!module) return 0;
    image_size = HudImageSize();
    if (image_size == 0) return 0;

    if (b->base_kind == CAMPAIGN_RACE_HUD_BASE_GUI_ARGUMENT) {
        if (b->target_rva != 0 || !game_mode_gui) return 0;
        base = (unsigned char*)game_mode_gui;
    } else if (b->base_kind == CAMPAIGN_PRESENTATION_BASE_MODULE_RVA) {
        if (b->target_rva == 0 || b->target_rva >= image_size) return 0;
        base = module + b->target_rva;
    } else {
        void** source;
        if (b->target_rva == 0 || b->target_rva >= image_size) return 0;
        source = (void**)(module + b->target_rva);
        if (!HudMemoryWritable(source, sizeof(void*))) {
            MEMORY_BASIC_INFORMATION mbi;
            if (VirtualQuery(source, &mbi, sizeof(mbi)) != sizeof(mbi) ||
                mbi.State != MEM_COMMIT ||
                (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS))) return 0;
        }
        base = (unsigned char*)*source;
        if (!base) return 0;
    }

    target = base + b->field_offset;
    if ((b->field_offset > 0 && target < base) ||
        (b->field_offset < 0 && target > base)) return 0;
    if (!HudMemoryWritable(target, size)) return 0;
    return target;
}

static int HudApplyFixed(const CampaignRaceHudBinding* b, int32_t value_x1000, void* game_mode_gui) {
    void* target;
    float f;

    if (!b) return 0;
    if (b->value_kind == CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED) {
        target = HudResolve(b, sizeof(float), game_mode_gui);
        if (!target) return 0;
        /*
          value_x1000 is the canonical HUD fixed-point representation.
          The target itself is a float, so writing the canonical value directly
          avoids 64-bit division helpers in the no-CRT x86 runtime.
        */
        f = (float)value_x1000 / 1000.0f;
        *(volatile float*)target = f;
        return 1;
    }

    if (b->value_kind == CAMPAIGN_PRESENTATION_VALUE_I32) {
        target = HudResolve(b, sizeof(int32_t), game_mode_gui);
        if (!target) return 0;
        *(volatile int32_t*)target = value_x1000;
        return 1;
    }
    if (b->value_kind == CAMPAIGN_PRESENTATION_VALUE_U32) {
        if (value_x1000 < 0) return 0;
        target = HudResolve(b, sizeof(uint32_t), game_mode_gui);
        if (!target) return 0;
        *(volatile uint32_t*)target = (uint32_t)value_x1000;
        return 1;
    }
    return 0;
}

static int HudApplyVisible(const CampaignRaceHudBinding* b, int32_t visible, void* game_mode_gui) {
    void* target;
    if (!b || (visible != 0 && visible != 1)) return 0;
    if (b->value_kind == CAMPAIGN_PRESENTATION_VALUE_U8_BOOL) {
        target = HudResolve(b, sizeof(unsigned char), game_mode_gui);
        if (!target) return 0;
        *(volatile unsigned char*)target = visible ? 1u : 0u;
        return 1;
    }
    if (b->value_kind == CAMPAIGN_PRESENTATION_VALUE_I32) {
        target = HudResolve(b, sizeof(int32_t), game_mode_gui);
        if (!target) return 0;
        *(volatile int32_t*)target = visible;
        return 1;
    }
    if (b->value_kind == CAMPAIGN_PRESENTATION_VALUE_U32) {
        target = HudResolve(b, sizeof(uint32_t), game_mode_gui);
        if (!target) return 0;
        *(volatile uint32_t*)target = visible ? 1u : 0u;
        return 1;
    }
    return 0;
}

int CampaignRaceHudApplyElementFromGui(
    void* game_mode_gui,
    const CampaignRaceHudElementState* state
) {
    const CampaignRaceHudBinding* b;

    if (!state || state->size < (uint32_t)sizeof(*state) ||
        !HudElementValid(state->element) || state->set_flags == 0) return 0;

    if (!CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_RACE_HUD)) return 0;
    if (!CampaignRaceHudElementReady(state->element, state->set_flags)) return 0;

    if (state->set_flags & CAMPAIGN_RACE_HUD_SET_X) {
        b = CampaignRaceHudBindingsFind(state->element, CAMPAIGN_RACE_HUD_PROP_X);
        if (!HudApplyFixed(b, state->x_x1000, game_mode_gui)) return 0;
    }
    if (state->set_flags & CAMPAIGN_RACE_HUD_SET_Y) {
        b = CampaignRaceHudBindingsFind(state->element, CAMPAIGN_RACE_HUD_PROP_Y);
        if (!HudApplyFixed(b, state->y_x1000, game_mode_gui)) return 0;
    }
    if (state->set_flags & CAMPAIGN_RACE_HUD_SET_SCALE) {
        if (state->scale_x1000 <= 0) return 0;
        b = CampaignRaceHudBindingsFind(state->element, CAMPAIGN_RACE_HUD_PROP_SCALE);
        if (!HudApplyFixed(b, state->scale_x1000, game_mode_gui)) return 0;
    }
    if (state->set_flags & CAMPAIGN_RACE_HUD_SET_OPACITY) {
        if (state->opacity_x1000 < 0 || state->opacity_x1000 > 1000) return 0;
        b = CampaignRaceHudBindingsFind(state->element, CAMPAIGN_RACE_HUD_PROP_OPACITY);
        if (!HudApplyFixed(b, state->opacity_x1000, game_mode_gui)) return 0;
    }
    if (state->set_flags & CAMPAIGN_RACE_HUD_SET_VISIBLE) {
        b = CampaignRaceHudBindingsFind(state->element, CAMPAIGN_RACE_HUD_PROP_VISIBLE);
        if (!HudApplyVisible(b, state->visible, game_mode_gui)) return 0;
    }
    return 1;
}

int CampaignRaceHudApplyElement(const CampaignRaceHudElementState* state) {
    return CampaignRaceHudApplyElementFromGui(0, state);
}

int _race_hud_fltused_anchor = 0;
