#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignPresentationBindings.h"
#include "CampaignPresentationCatalog.h"

#define RXPB_MAGIC 0x42505852u /* RXPB */
#define RXPB_VERSION 1u

typedef struct CampaignPresentationBindingFileHeader {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t entry_size;
    uint32_t entries_hash;
} CampaignPresentationBindingFileHeader;

static CampaignPresentationBinding g_bindings[CAMPAIGN_PRESENTATION_BINDING_MAX];
static CampaignPresentationBinding g_load_bindings[CAMPAIGN_PRESENTATION_BINDING_MAX];
static uint32_t g_binding_count;
static volatile LONG g_bindings_loaded;
static WCHAR g_binding_path[1024];

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
    uint32_t h = 2166136261u;
    uint32_t i;
    for (i = 0; i < count; ++i) {
        h ^= data[i];
        h *= 16777619u;
    }
    return h;
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

static int BuildBindingPath(void) {
    DWORD n;
    int i;
    static const WCHAR suffix[] = L"CampaignPresentationBindings.dat";
    uint32_t pos;
    uint32_t j = 0;

    ZeroBytes(g_binding_path, (uint32_t)sizeof(g_binding_path));
    n = GetModuleFileNameW(0, g_binding_path, 1024);
    if (n == 0 || n >= 1024) return 0;

    i = (int)n - 1;
    while (i >= 0 && g_binding_path[i] != L'\\' && g_binding_path[i] != L'/') --i;
    if (i < 0) return 0;
    pos = (uint32_t)(i + 1);

    while (suffix[j]) {
        if (pos + 1 >= 1024) return 0;
        g_binding_path[pos++] = suffix[j++];
    }
    g_binding_path[pos] = 0;
    return 1;
}

static int BindingIdValid(const CampaignPresentationBinding* binding) {
    uint32_t i;
    if (!binding || !binding->id[0]) return 0;
    for (i = 0; i < CAMPAIGN_PRESENTATION_BINDING_ID_MAX; ++i) {
        if (binding->id[i] == 0) return 1;
    }
    return 0;
}

static int ValidateBinding(const CampaignPresentationBinding* binding) {
    const CampaignPresentationCapability* capability;

    if (!BindingIdValid(binding)) return 0;
    if (!(binding->flags & CAMPAIGN_PRESENTATION_BINDING_VERIFIED)) return 0;
    if (binding->target_rva == 0) return 0;

    if (binding->base_kind != CAMPAIGN_PRESENTATION_BASE_MODULE_RVA &&
        binding->base_kind != CAMPAIGN_PRESENTATION_BASE_POINTER_RVA) {
        return 0;
    }

    if (binding->value_kind != CAMPAIGN_PRESENTATION_VALUE_I32 &&
        binding->value_kind != CAMPAIGN_PRESENTATION_VALUE_U32 &&
        binding->value_kind != CAMPAIGN_PRESENTATION_VALUE_U8_BOOL &&
        binding->value_kind != CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED) {
        return 0;
    }

    if (binding->value_kind == CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED) {
        if (binding->scale_divisor <= 0) return 0;
    } else if (binding->scale_divisor != 1) {
        return 0;
    }

    capability = CampaignPresentationCatalogFind(binding->id);
    if (!capability) return 0;
    if (!(capability->flags & CAMPAIGN_PRESENTATION_CAPABILITY_VERIFIED)) return 0;
    return 1;
}

int CampaignPresentationBindingsLoad(void) {
    HANDLE h;
    DWORD got = 0;
    CampaignPresentationBindingFileHeader header;
    CampaignPresentationBinding* temp = g_load_bindings;
    uint32_t i;

    ZeroBytes(g_bindings, (uint32_t)sizeof(g_bindings));
    ZeroBytes(g_load_bindings, (uint32_t)sizeof(g_load_bindings));
    g_binding_count = 0;
    InterlockedExchange(&g_bindings_loaded, 0);

    if (!BuildBindingPath()) return 0;

    h = CreateFileW(
        g_binding_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        0
    );

    /*
      Missing binding catalog is safe: no renderer/camera memory is writable
      through ReXtreme until a verified catalog exists.
    */
    if (h == INVALID_HANDLE_VALUE) {
        InterlockedExchange(&g_bindings_loaded, 1);
        return 1;
    }

    ZeroBytes(&header, (uint32_t)sizeof(header));
    if (!ReadFile(h, &header, (DWORD)sizeof(header), &got, 0) ||
        got != (DWORD)sizeof(header) ||
        header.magic != RXPB_MAGIC ||
        header.version != RXPB_VERSION ||
        header.entry_size != (uint32_t)sizeof(CampaignPresentationBinding) ||
        header.count > CAMPAIGN_PRESENTATION_BINDING_MAX) {
        CloseHandle(h);
        return 0;
    }

    if (header.count > 0) {
        DWORD bytes = (DWORD)(header.count * (uint32_t)sizeof(CampaignPresentationBinding));
        got = 0;
        if (!ReadFile(h, temp, bytes, &got, 0) || got != bytes) {
            CloseHandle(h);
            return 0;
        }
        if (header.entries_hash != Fnv1a((const unsigned char*)temp, bytes)) {
            CloseHandle(h);
            return 0;
        }
    } else if (header.entries_hash != Fnv1a((const unsigned char*)temp, 0)) {
        CloseHandle(h);
        return 0;
    }
    CloseHandle(h);

    for (i = 0; i < header.count; ++i) {
        uint32_t j;
        if (!ValidateBinding(&temp[i])) return 0;
        for (j = 0; j < i; ++j) {
            if (StringEqual(temp[i].id, temp[j].id)) return 0;
        }
    }

    for (i = 0; i < header.count; ++i) {
        CopyBytes(&g_bindings[i], &temp[i], (uint32_t)sizeof(temp[i]));
    }
    g_binding_count = header.count;
    InterlockedExchange(&g_bindings_loaded, 1);
    return 1;
}

static void EnsureLoaded(void) {
    if (InterlockedCompareExchange(&g_bindings_loaded, 1, 1) == 0) {
        CampaignPresentationBindingsLoad();
    }
}

uint32_t CampaignPresentationBindingsCount(void) {
    EnsureLoaded();
    return g_binding_count;
}

const CampaignPresentationBinding* CampaignPresentationBindingsFind(const char* id) {
    uint32_t i;
    if (!id || !id[0]) return 0;
    EnsureLoaded();
    for (i = 0; i < g_binding_count; ++i) {
        if (StringEqual(g_bindings[i].id, id)) return &g_bindings[i];
    }
    return 0;
}

static int MemoryRangeHasAccess(const void* address, SIZE_T size, int write) {
    MEMORY_BASIC_INFORMATION mbi;
    uintptr_t begin;
    uintptr_t end;
    uintptr_t region_end;
    DWORD protect;
    int writable;

    if (!address || size == 0) return 0;
    if (VirtualQuery(address, &mbi, sizeof(mbi)) != sizeof(mbi)) return 0;
    if (mbi.State != MEM_COMMIT) return 0;
    if (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS)) return 0;

    begin = (uintptr_t)address;
    end = begin + size;
    if (end < begin) return 0;
    region_end = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;
    if (end > region_end) return 0;

    if (!write) return 1;

    protect = mbi.Protect & 0xFFu;
    writable =
        protect == PAGE_READWRITE ||
        protect == PAGE_WRITECOPY ||
        protect == PAGE_EXECUTE_READWRITE ||
        protect == PAGE_EXECUTE_WRITECOPY;
    return writable ? 1 : 0;
}

static void* ResolveBindingTarget(const CampaignPresentationBinding* binding, uint32_t size, int write) {
    unsigned char* module;
    unsigned char* target;

    if (!binding) return 0;
    module = (unsigned char*)GetModuleHandleW(0);
    if (!module) return 0;

    if (binding->base_kind == CAMPAIGN_PRESENTATION_BASE_MODULE_RVA) {
        target = module + binding->target_rva + binding->field_offset;
    } else {
        void** source = (void**)(module + binding->target_rva);
        void* base;
        if (!MemoryRangeHasAccess(source, sizeof(void*), 0)) return 0;
        base = *source;
        if (!base) return 0;
        target = (unsigned char*)base + binding->field_offset;
    }

    if (!MemoryRangeHasAccess(target, size, write)) return 0;
    return target;
}

int CampaignPresentationBindingsRead(const char* id, int32_t* out_value) {
    const CampaignPresentationBinding* binding;
    void* target;

    if (!out_value) return 0;
    binding = CampaignPresentationBindingsFind(id);
    if (!binding) return 0;

    switch (binding->value_kind) {
    case CAMPAIGN_PRESENTATION_VALUE_I32:
        target = ResolveBindingTarget(binding, sizeof(int32_t), 0);
        if (!target) return 0;
        *out_value = *(volatile int32_t*)target;
        return 1;
    case CAMPAIGN_PRESENTATION_VALUE_U32:
        target = ResolveBindingTarget(binding, sizeof(uint32_t), 0);
        if (!target) return 0;
        *out_value = (int32_t)*(volatile uint32_t*)target;
        return 1;
    case CAMPAIGN_PRESENTATION_VALUE_U8_BOOL:
        target = ResolveBindingTarget(binding, sizeof(unsigned char), 0);
        if (!target) return 0;
        *out_value = *(volatile unsigned char*)target ? 1 : 0;
        return 1;
    case CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED:
        {
            float value;
            target = ResolveBindingTarget(binding, sizeof(float), 0);
            if (!target) return 0;
            value = *(volatile float*)target;
            if (value >= 0.0f) {
                *out_value = (int32_t)(value * (float)binding->scale_divisor + 0.5f);
            } else {
                *out_value = (int32_t)(value * (float)binding->scale_divisor - 0.5f);
            }
            return 1;
        }
    default:
        return 0;
    }
}

int CampaignPresentationBindingsApply(const char* id, int32_t value) {
    const CampaignPresentationBinding* binding;
    const CampaignPresentationCapability* capability;
    void* target;

    binding = CampaignPresentationBindingsFind(id);
    capability = CampaignPresentationCatalogFind(id);
    if (!binding || !capability) return 0;
    if (!CampaignPresentationCapabilityValueValid(capability, value)) return 0;

    switch (binding->value_kind) {
    case CAMPAIGN_PRESENTATION_VALUE_I32:
        target = ResolveBindingTarget(binding, sizeof(int32_t), 1);
        if (!target) return 0;
        *(volatile int32_t*)target = value;
        return 1;
    case CAMPAIGN_PRESENTATION_VALUE_U32:
        if (value < 0) return 0;
        target = ResolveBindingTarget(binding, sizeof(uint32_t), 1);
        if (!target) return 0;
        *(volatile uint32_t*)target = (uint32_t)value;
        return 1;
    case CAMPAIGN_PRESENTATION_VALUE_U8_BOOL:
        if (value != 0 && value != 1) return 0;
        target = ResolveBindingTarget(binding, sizeof(unsigned char), 1);
        if (!target) return 0;
        *(volatile unsigned char*)target = (unsigned char)value;
        return 1;
    case CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED:
        target = ResolveBindingTarget(binding, sizeof(float), 1);
        if (!target || binding->scale_divisor <= 0) return 0;
        *(volatile float*)target = (float)value / (float)binding->scale_divisor;
        return 1;
    default:
        return 0;
    }
}
