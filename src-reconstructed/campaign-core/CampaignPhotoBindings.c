#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignPhotoBindings.h"

#define RXPH_MAGIC 0x48505852u /* RXPH */
#define RXPH_VERSION 1u
#define CAMPAIGN_PHOTO_BINDING_VERIFIED 1u

typedef struct CampaignPhotoBindingFileHeader {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t entry_size;
    uint32_t entries_hash;
} CampaignPhotoBindingFileHeader;

static CampaignPhotoBinding g_bindings[CAMPAIGN_PHOTO_BINDING_MAX];
static CampaignPhotoBinding g_load_bindings[CAMPAIGN_PHOTO_BINDING_MAX];
static uint32_t g_count;
static volatile LONG g_loaded;
static WCHAR g_path[1024];

static void ZeroBytes(void* p, uint32_t count) {
    volatile unsigned char* q = (volatile unsigned char*)p;
    uint32_t i;
    for (i = 0; i < count; ++i) q[i] = 0;
}

static uint32_t Fnv1a(const unsigned char* data, uint32_t count) {
    uint32_t h = 2166136261u, i;
    for (i = 0; i < count; ++i) {
        h ^= data[i];
        h *= 16777619u;
    }
    return h;
}

static int BuildPath(void) {
    DWORD n;
    int i;
    static const WCHAR suffix[] = L"CampaignPhotoBindings.dat";
    uint32_t pos, j = 0;

    ZeroBytes(g_path, (uint32_t)sizeof(g_path));
    n = GetModuleFileNameW(0, g_path, 1024);
    if (n == 0 || n >= 1024) return 0;
    i = (int)n - 1;
    while (i >= 0 && g_path[i] != L'\\' && g_path[i] != L'/') --i;
    if (i < 0) return 0;
    pos = (uint32_t)(i + 1);
    while (suffix[j]) {
        if (pos + 1 >= 1024) return 0;
        g_path[pos++] = suffix[j++];
    }
    g_path[pos] = 0;
    return 1;
}

static int SemanticValid(uint32_t semantic) {
    return semantic >= CAMPAIGN_PHOTO_BIND_POSITION_X &&
           semantic <= CAMPAIGN_PHOTO_BIND_HUD_VISIBLE;
}

static int BindingValid(const CampaignPhotoBinding* b) {
    if (!b || !SemanticValid(b->semantic)) return 0;
    if (!(b->flags & CAMPAIGN_PHOTO_BINDING_VERIFIED)) return 0;
    if (b->target_rva == 0) return 0;
    if (b->base_kind != CAMPAIGN_PRESENTATION_BASE_MODULE_RVA &&
        b->base_kind != CAMPAIGN_PRESENTATION_BASE_POINTER_RVA) return 0;
    if (b->value_kind != CAMPAIGN_PRESENTATION_VALUE_I32 &&
        b->value_kind != CAMPAIGN_PRESENTATION_VALUE_U32 &&
        b->value_kind != CAMPAIGN_PRESENTATION_VALUE_U8_BOOL &&
        b->value_kind != CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED) return 0;
    if (b->value_kind == CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED) {
        if (b->scale_divisor <= 0) return 0;
    } else if (b->scale_divisor != 1) {
        return 0;
    }
    return 1;
}

int CampaignPhotoBindingsLoad(void) {
    HANDLE h;
    DWORD got = 0;
    CampaignPhotoBindingFileHeader header;
    uint32_t i;

    ZeroBytes(g_bindings, (uint32_t)sizeof(g_bindings));
    ZeroBytes(g_load_bindings, (uint32_t)sizeof(g_load_bindings));
    g_count = 0;
    InterlockedExchange(&g_loaded, 0);

    if (!BuildPath()) return 0;
    h = CreateFileW(g_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0,
                    OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_loaded, 1);
        return 1;
    }

    ZeroBytes(&header, (uint32_t)sizeof(header));
    if (!ReadFile(h, &header, (DWORD)sizeof(header), &got, 0) ||
        got != (DWORD)sizeof(header) ||
        header.magic != RXPH_MAGIC ||
        header.version != RXPH_VERSION ||
        header.entry_size != (uint32_t)sizeof(CampaignPhotoBinding) ||
        header.count > CAMPAIGN_PHOTO_BINDING_MAX) {
        CloseHandle(h);
        return 0;
    }

    if (header.count > 0) {
        DWORD bytes = (DWORD)(header.count * (uint32_t)sizeof(CampaignPhotoBinding));
        got = 0;
        if (!ReadFile(h, g_load_bindings, bytes, &got, 0) || got != bytes ||
            header.entries_hash != Fnv1a((const unsigned char*)g_load_bindings, bytes)) {
            CloseHandle(h);
            return 0;
        }
    } else if (header.entries_hash != Fnv1a((const unsigned char*)g_load_bindings, 0)) {
        CloseHandle(h);
        return 0;
    }
    CloseHandle(h);

    for (i = 0; i < header.count; ++i) {
        uint32_t j;
        if (!BindingValid(&g_load_bindings[i])) return 0;
        for (j = 0; j < i; ++j) {
            if (g_load_bindings[i].semantic == g_load_bindings[j].semantic) return 0;
        }
        g_bindings[i] = g_load_bindings[i];
    }

    g_count = header.count;
    InterlockedExchange(&g_loaded, 1);
    return 1;
}

static void EnsureLoaded(void) {
    if (InterlockedCompareExchange(&g_loaded, 1, 1) == 0) CampaignPhotoBindingsLoad();
}

uint32_t CampaignPhotoBindingsCount(void) {
    EnsureLoaded();
    return g_count;
}

const CampaignPhotoBinding* CampaignPhotoBindingsFind(uint32_t semantic) {
    uint32_t i;
    EnsureLoaded();
    for (i = 0; i < g_count; ++i) {
        if (g_bindings[i].semantic == semantic) return &g_bindings[i];
    }
    return 0;
}

static int MemoryRangeHasAccess(const void* address, SIZE_T size, int write) {
    MEMORY_BASIC_INFORMATION mbi;
    uintptr_t begin, end, region_end;
    DWORD protect;

    if (!address || size == 0) return 0;
    if (VirtualQuery(address, &mbi, sizeof(mbi)) != sizeof(mbi)) return 0;
    if (mbi.State != MEM_COMMIT || (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS))) return 0;
    begin = (uintptr_t)address;
    end = begin + size;
    if (end < begin) return 0;
    region_end = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;
    if (end > region_end) return 0;
    if (!write) return 1;

    protect = mbi.Protect & 0xFFu;
    return protect == PAGE_READWRITE ||
           protect == PAGE_WRITECOPY ||
           protect == PAGE_EXECUTE_READWRITE ||
           protect == PAGE_EXECUTE_WRITECOPY;
}

static void* ResolveTarget(const CampaignPhotoBinding* b, uint32_t size) {
    unsigned char* module;
    unsigned char* target;
    if (!b) return 0;
    module = (unsigned char*)GetModuleHandleW(0);
    if (!module) return 0;

    if (b->base_kind == CAMPAIGN_PRESENTATION_BASE_MODULE_RVA) {
        target = module + b->target_rva + b->field_offset;
    } else {
        void** source = (void**)(module + b->target_rva);
        void* base;
        if (!MemoryRangeHasAccess(source, sizeof(void*), 0)) return 0;
        base = *source;
        if (!base) return 0;
        target = (unsigned char*)base + b->field_offset;
    }
    return MemoryRangeHasAccess(target, size, 1) ? target : 0;
}

static int ApplyInteger(const CampaignPhotoBinding* b, int32_t value) {
    void* target;
    switch (b->value_kind) {
    case CAMPAIGN_PRESENTATION_VALUE_I32:
        target = ResolveTarget(b, sizeof(int32_t));
        if (!target) return 0;
        *(volatile int32_t*)target = value;
        return 1;
    case CAMPAIGN_PRESENTATION_VALUE_U32:
        if (value < 0) return 0;
        target = ResolveTarget(b, sizeof(uint32_t));
        if (!target) return 0;
        *(volatile uint32_t*)target = (uint32_t)value;
        return 1;
    case CAMPAIGN_PRESENTATION_VALUE_U8_BOOL:
        if (value != 0 && value != 1) return 0;
        target = ResolveTarget(b, sizeof(unsigned char));
        if (!target) return 0;
        *(volatile unsigned char*)target = (unsigned char)value;
        return 1;
    case CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED:
        target = ResolveTarget(b, sizeof(float));
        if (!target || b->scale_divisor <= 0) return 0;
        *(volatile float*)target = (float)value / (float)b->scale_divisor;
        return 1;
    default:
        return 0;
    }
}

static int ApplySemantic(uint32_t semantic, int32_t value) {
    const CampaignPhotoBinding* b = CampaignPhotoBindingsFind(semantic);
    if (!b) return 0;
    return ApplyInteger(b, value);
}

int CampaignPhotoBindingsReady(uint32_t camera_mode) {
    if (camera_mode != CAMPAIGN_PHOTO_CAMERA_FREE) return 0;
    return CampaignPhotoBindingsFind(CAMPAIGN_PHOTO_BIND_POSITION_X) &&
           CampaignPhotoBindingsFind(CAMPAIGN_PHOTO_BIND_POSITION_Y) &&
           CampaignPhotoBindingsFind(CAMPAIGN_PHOTO_BIND_POSITION_Z) &&
           CampaignPhotoBindingsFind(CAMPAIGN_PHOTO_BIND_PITCH) &&
           CampaignPhotoBindingsFind(CAMPAIGN_PHOTO_BIND_YAW) &&
           CampaignPhotoBindingsFind(CAMPAIGN_PHOTO_BIND_ROLL) &&
           CampaignPhotoBindingsFind(CAMPAIGN_PHOTO_BIND_HUD_VISIBLE);
}

static int FloatToScaled(float value, int32_t scale, int32_t* out) {
    float scaled;
    if (!out || scale <= 0) return 0;
    scaled = value * (float)scale;
    if (scaled > 2147483000.0f || scaled < -2147483000.0f) return 0;
    *out = scaled >= 0.0f ? (int32_t)(scaled + 0.5f) : (int32_t)(scaled - 0.5f);
    return 1;
}

int CampaignPhotoBindingsApply(const CampaignPhotoState* state) {
    int32_t x, y, z;
    const CampaignPhotoBinding* bx;
    const CampaignPhotoBinding* by;
    const CampaignPhotoBinding* bz;

    if (!state || state->size < (uint32_t)sizeof(*state) || !state->active) return 0;
    if (!CampaignPhotoBindingsReady(state->camera_mode)) return 0;

    bx = CampaignPhotoBindingsFind(CAMPAIGN_PHOTO_BIND_POSITION_X);
    by = CampaignPhotoBindingsFind(CAMPAIGN_PHOTO_BIND_POSITION_Y);
    bz = CampaignPhotoBindingsFind(CAMPAIGN_PHOTO_BIND_POSITION_Z);
    if (!bx || !by || !bz) return 0;

    /*
      Position scale follows each binding's declared float scale. For integer
      targets, millimeters (x1000) are used as the canonical fixed-point form.
    */
    if (!FloatToScaled(state->position_x,
            bx->value_kind == CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED ? bx->scale_divisor : 1000,
            &x) ||
        !FloatToScaled(state->position_y,
            by->value_kind == CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED ? by->scale_divisor : 1000,
            &y) ||
        !FloatToScaled(state->position_z,
            bz->value_kind == CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED ? bz->scale_divisor : 1000,
            &z)) return 0;

    if (!ApplySemantic(CAMPAIGN_PHOTO_BIND_POSITION_X, x) ||
        !ApplySemantic(CAMPAIGN_PHOTO_BIND_POSITION_Y, y) ||
        !ApplySemantic(CAMPAIGN_PHOTO_BIND_POSITION_Z, z) ||
        !ApplySemantic(CAMPAIGN_PHOTO_BIND_PITCH, state->pitch_x100) ||
        !ApplySemantic(CAMPAIGN_PHOTO_BIND_YAW, state->yaw_x100) ||
        !ApplySemantic(CAMPAIGN_PHOTO_BIND_ROLL, state->roll_x100) ||
        !ApplySemantic(CAMPAIGN_PHOTO_BIND_HUD_VISIBLE, state->hide_hud ? 0 : 1)) {
        return 0;
    }

    if (state->fov_x100 != 0) {
        const CampaignPhotoBinding* fov = CampaignPhotoBindingsFind(CAMPAIGN_PHOTO_BIND_FOV);
        if (!fov || !ApplyInteger(fov, state->fov_x100)) return 0;
    }
    return 1;
}

/* See CampaignPresentationBindings.c: local no-CRT float marker. */
int _photo_fltused_anchor = 0;
