#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignReplayBindings.h"

#define RXRB_MAGIC 0x42525852u /* RXRB */
#define RXRB_VERSION 1u

typedef struct CampaignReplayBindingFileHeader {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t entry_size;
    uint32_t entries_hash;
    uint32_t pe_time_date_stamp;
    uint32_t pe_size_of_image;
} CampaignReplayBindingFileHeader;

static CampaignReplayBinding g_bindings[CAMPAIGN_REPLAY_BINDING_MAX];
static CampaignReplayBinding g_load_bindings[CAMPAIGN_REPLAY_BINDING_MAX];
static uint32_t g_count;
static volatile LONG g_loaded;
static WCHAR g_path[1024];

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
    uint32_t pos, j = 0;
    static const WCHAR suffix[] = L"CampaignReplayBindings.dat";

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

static int CurrentExecutableMatches(
    uint32_t expected_time_date_stamp,
    uint32_t expected_size_of_image
) {
    unsigned char* module;
    uint32_t pe_off;
    unsigned char* pe;

    module = (unsigned char*)GetModuleHandleW(0);
    if (!module || module[0] != 'M' || module[1] != 'Z') return 0;
    pe_off = *(uint32_t*)(module + 0x3C);
    pe = module + pe_off;
    if (pe[0] != 'P' || pe[1] != 'E' || pe[2] != 0 || pe[3] != 0) return 0;
    if (*(uint16_t*)(pe + 24) != 0x010B) return 0;

    return *(uint32_t*)(pe + 8) == expected_time_date_stamp &&
           *(uint32_t*)(pe + 24 + 56) == expected_size_of_image;
}

static int SemanticValid(uint32_t semantic) {
    return semantic >= CAMPAIGN_REPLAY_BIND_TIME_MS &&
           semantic <= CAMPAIGN_REPLAY_BIND_STATE_FLAGS;
}

static int BindingValid(const CampaignReplayBinding* b) {
    if (!b || !SemanticValid(b->semantic)) return 0;
    if (!(b->flags & CAMPAIGN_REPLAY_BINDING_VERIFIED)) return 0;
    if (b->root_kind != CAMPAIGN_REPLAY_ROOT_GUI_ARGUMENT &&
        b->root_kind != CAMPAIGN_REPLAY_ROOT_MODULE_RVA &&
        b->root_kind != CAMPAIGN_REPLAY_ROOT_POINTER_RVA) return 0;
    if (b->root_kind != CAMPAIGN_REPLAY_ROOT_GUI_ARGUMENT && b->root_rva == 0) return 0;
    if (b->chain_count > CAMPAIGN_REPLAY_BINDING_CHAIN_MAX) return 0;

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

static int MemoryRangeReadable(const void* address, SIZE_T size) {
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

int CampaignReplayBindingsLoad(void) {
    HANDLE h;
    DWORD got = 0;
    CampaignReplayBindingFileHeader header;
    uint32_t i, j;

    ZeroBytes(g_bindings, (uint32_t)sizeof(g_bindings));
    ZeroBytes(g_load_bindings, (uint32_t)sizeof(g_load_bindings));
    g_count = 0;
    InterlockedExchange(&g_loaded, 0);

    if (!BuildPath()) return 0;

    h = CreateFileW(
        g_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );

    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_loaded, 1);
        return 1;
    }

    ZeroBytes(&header, (uint32_t)sizeof(header));
    if (!ReadFile(h, &header, (DWORD)sizeof(header), &got, 0) ||
        got != (DWORD)sizeof(header) ||
        header.magic != RXRB_MAGIC ||
        header.version != RXRB_VERSION ||
        header.entry_size != (uint32_t)sizeof(CampaignReplayBinding) ||
        header.count > CAMPAIGN_REPLAY_BINDING_MAX) {
        CloseHandle(h);
        return 0;
    }

    if (header.count > 0 &&
        !CurrentExecutableMatches(header.pe_time_date_stamp, header.pe_size_of_image)) {
        CloseHandle(h);
        return 0;
    }

    if (header.count > 0) {
        DWORD bytes = (DWORD)(header.count * (uint32_t)sizeof(CampaignReplayBinding));
        got = 0;
        if (!ReadFile(h, g_load_bindings, bytes, &got, 0) || got != bytes) {
            CloseHandle(h);
            return 0;
        }
        if (header.entries_hash != Fnv1a((const unsigned char*)g_load_bindings, bytes)) {
            CloseHandle(h);
            return 0;
        }
    } else if (header.entries_hash != Fnv1a((const unsigned char*)g_load_bindings, 0)) {
        CloseHandle(h);
        return 0;
    }
    CloseHandle(h);

    for (i = 0; i < header.count; ++i) {
        if (!BindingValid(&g_load_bindings[i])) return 0;
        for (j = 0; j < i; ++j) {
            if (g_load_bindings[i].semantic == g_load_bindings[j].semantic) return 0;
        }
    }

    for (i = 0; i < header.count; ++i) {
        CopyBytes(&g_bindings[i], &g_load_bindings[i], (uint32_t)sizeof(g_bindings[i]));
    }
    g_count = header.count;
    InterlockedExchange(&g_loaded, 1);
    return 1;
}

static void EnsureLoaded(void) {
    if (InterlockedCompareExchange(&g_loaded, 1, 1) == 0) {
        CampaignReplayBindingsLoad();
    }
}

uint32_t CampaignReplayBindingsCount(void) {
    EnsureLoaded();
    return g_count;
}

const CampaignReplayBinding* CampaignReplayBindingsFind(uint32_t semantic) {
    uint32_t i;
    if (!SemanticValid(semantic)) return 0;
    EnsureLoaded();
    for (i = 0; i < g_count; ++i) {
        if (g_bindings[i].semantic == semantic) return &g_bindings[i];
    }
    return 0;
}

static int Required(uint32_t semantic) {
    const CampaignReplayBinding* b = CampaignReplayBindingsFind(semantic);
    return b && !(b->flags & CAMPAIGN_REPLAY_BINDING_OPTIONAL);
}

int CampaignReplayBindingsReady(void) {
    return Required(CAMPAIGN_REPLAY_BIND_TIME_MS) &&
           Required(CAMPAIGN_REPLAY_BIND_ENTITY_ID) &&
           Required(CAMPAIGN_REPLAY_BIND_POSITION_X) &&
           Required(CAMPAIGN_REPLAY_BIND_POSITION_Y) &&
           Required(CAMPAIGN_REPLAY_BIND_POSITION_Z) &&
           Required(CAMPAIGN_REPLAY_BIND_ROTATION_X) &&
           Required(CAMPAIGN_REPLAY_BIND_ROTATION_Y) &&
           Required(CAMPAIGN_REPLAY_BIND_ROTATION_Z) &&
           Required(CAMPAIGN_REPLAY_BIND_ROTATION_W);
}

static void* ResolveRoot(const CampaignReplayBinding* b, void* game_mode_gui) {
    unsigned char* module;
    void* root;

    if (!b) return 0;

    if (b->root_kind == CAMPAIGN_REPLAY_ROOT_GUI_ARGUMENT) {
        return game_mode_gui;
    }

    module = (unsigned char*)GetModuleHandleW(0);
    if (!module) return 0;

    if (b->root_kind == CAMPAIGN_REPLAY_ROOT_MODULE_RVA) {
        return module + b->root_rva;
    }

    {
        void** source = (void**)(module + b->root_rva);
        if (!MemoryRangeReadable(source, sizeof(void*))) return 0;
        root = *source;
        return root;
    }
}

static void* ResolveValueAddress(const CampaignReplayBinding* b, void* game_mode_gui) {
    unsigned char* current;
    uint32_t i;

    current = (unsigned char*)ResolveRoot(b, game_mode_gui);
    if (!current) return 0;

    for (i = 0; i < b->chain_count; ++i) {
        void** source = (void**)(current + b->chain_offsets[i]);
        if (!MemoryRangeReadable(source, sizeof(void*))) return 0;
        current = (unsigned char*)*source;
        if (!current) return 0;
    }

    current += b->field_offset;
    return current;
}

static int ReplayReadRaw(const CampaignReplayBinding* b, void* game_mode_gui, int32_t* out) {
    void* target;
    float f;

    if (!b || !out) return 0;

    switch (b->value_kind) {
    case CAMPAIGN_PRESENTATION_VALUE_I32:
        target = ResolveValueAddress(b, game_mode_gui);
        if (!MemoryRangeReadable(target, sizeof(int32_t))) return 0;
        *out = *(volatile int32_t*)target;
        return 1;
    case CAMPAIGN_PRESENTATION_VALUE_U32:
        target = ResolveValueAddress(b, game_mode_gui);
        if (!MemoryRangeReadable(target, sizeof(uint32_t))) return 0;
        *out = (int32_t)*(volatile uint32_t*)target;
        return 1;
    case CAMPAIGN_PRESENTATION_VALUE_U8_BOOL:
        target = ResolveValueAddress(b, game_mode_gui);
        if (!MemoryRangeReadable(target, sizeof(unsigned char))) return 0;
        *out = *(volatile unsigned char*)target ? 1 : 0;
        return 1;
    case CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED:
        target = ResolveValueAddress(b, game_mode_gui);
        if (!MemoryRangeReadable(target, sizeof(float))) return 0;
        f = *(volatile float*)target;
        if (f > 2147483000.0f || f < -2147483000.0f) return 0;
        if (f >= 0.0f) {
            *out = (int32_t)(f * (float)b->scale_divisor + 0.5f);
        } else {
            *out = (int32_t)(f * (float)b->scale_divisor - 0.5f);
        }
        return 1;
    default:
        return 0;
    }
}

static int ReadFloatSemantic(
    uint32_t semantic,
    void* game_mode_gui,
    float* out
) {
    const CampaignReplayBinding* b;
    int32_t raw;
    int32_t scale;

    if (!out) return 0;
    b = CampaignReplayBindingsFind(semantic);
    if (!b || !ReplayReadRaw(b, game_mode_gui, &raw)) return 0;

    scale = b->value_kind == CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED ?
        b->scale_divisor : 1000;
    if (scale <= 0) return 0;
    *out = (float)raw / (float)scale;
    return 1;
}

int CampaignReplayBindingsSample(void* game_mode_gui, CampaignReplaySample* out) {
    int32_t raw;
    const CampaignReplayBinding* optional;

    if (!game_mode_gui || !out || !CampaignReplayBindingsReady()) return 0;
    ZeroBytes(out, (uint32_t)sizeof(*out));

    if (!ReplayReadRaw(CampaignReplayBindingsFind(CAMPAIGN_REPLAY_BIND_TIME_MS), game_mode_gui, &raw)) return 0;
    if (raw < 0) return 0;
    out->time_ms = (uint32_t)raw;

    if (!ReplayReadRaw(CampaignReplayBindingsFind(CAMPAIGN_REPLAY_BIND_ENTITY_ID), game_mode_gui, &out->entity_id)) return 0;

    if (!ReadFloatSemantic(CAMPAIGN_REPLAY_BIND_POSITION_X, game_mode_gui, &out->position_x) ||
        !ReadFloatSemantic(CAMPAIGN_REPLAY_BIND_POSITION_Y, game_mode_gui, &out->position_y) ||
        !ReadFloatSemantic(CAMPAIGN_REPLAY_BIND_POSITION_Z, game_mode_gui, &out->position_z) ||
        !ReadFloatSemantic(CAMPAIGN_REPLAY_BIND_ROTATION_X, game_mode_gui, &out->rotation_x) ||
        !ReadFloatSemantic(CAMPAIGN_REPLAY_BIND_ROTATION_Y, game_mode_gui, &out->rotation_y) ||
        !ReadFloatSemantic(CAMPAIGN_REPLAY_BIND_ROTATION_Z, game_mode_gui, &out->rotation_z) ||
        !ReadFloatSemantic(CAMPAIGN_REPLAY_BIND_ROTATION_W, game_mode_gui, &out->rotation_w)) {
        return 0;
    }

    optional = CampaignReplayBindingsFind(CAMPAIGN_REPLAY_BIND_VELOCITY_X);
    if (optional && !ReadFloatSemantic(CAMPAIGN_REPLAY_BIND_VELOCITY_X, game_mode_gui, &out->velocity_x)) return 0;
    optional = CampaignReplayBindingsFind(CAMPAIGN_REPLAY_BIND_VELOCITY_Y);
    if (optional && !ReadFloatSemantic(CAMPAIGN_REPLAY_BIND_VELOCITY_Y, game_mode_gui, &out->velocity_y)) return 0;
    optional = CampaignReplayBindingsFind(CAMPAIGN_REPLAY_BIND_VELOCITY_Z);
    if (optional && !ReadFloatSemantic(CAMPAIGN_REPLAY_BIND_VELOCITY_Z, game_mode_gui, &out->velocity_z)) return 0;

    optional = CampaignReplayBindingsFind(CAMPAIGN_REPLAY_BIND_STATE_FLAGS);
    if (optional) {
        if (!ReplayReadRaw(optional, game_mode_gui, &raw) || raw < 0) return 0;
        out->state_flags = (uint32_t)raw;
    }

    return 1;
}

/* Separate no-CRT translation unit still needs the floating-point marker. */
int _replay_fltused_anchor = 0;
