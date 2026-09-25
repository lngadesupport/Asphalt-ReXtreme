#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>

#include "RexIgpProxy.h"

static int failures = 0;
#define CHECK(expr) do { if (!(expr)) { \
    printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #expr); \
    failures += 1; \
} } while (0)

static void test_proxy_exposes_game_import_surface(void) {
    static const char* names[] = {
        "?AddIGPComponent@IGPControl@IGPLib@@QAEXPBD@Z",
        "?DestroyIGP@IGPControl@IGPLib@@SAXXZ",
        "?GetInstance@IGPControl@IGPLib@@SAPAV12@XZ",
        "?HttpPostLink@IGPControl@IGPLib@@QAEXPBD@Z",
        "?Init@IGPControl@IGPLib@@SAXABUInitParams@2@@Z",
        "?InitBridgeCallbacks@IGPLib@@YAXXZ",
        "?InitBridgeClass@IGPLib@@YAXP$AAVPanel@Controls@Xaml@UI@Windows@@@Z",
        "?IsOnScreenFreemium@IGPControl@IGPLib@@SA_NXZ",
        "?PauseIGP@IGPControl@IGPLib@@QAEXXZ",
        "?ResumeIGP@IGPControl@IGPLib@@QAEXXZ",
        "?SetGender@IGPControl@IGPLib@@SAXPBD@Z",
        "?SetIGPLanguage@IGPControl@IGPLib@@QAEXPBD@Z",
        "?SetUserAge@IGPControl@IGPLib@@SAXPBD@Z",
        "?ShowIGP@IGPControl@IGPLib@@QAEX_N@Z"
    };
    HMODULE module = LoadLibraryA("IGPLib_x86.dll");
    size_t i;

    CHECK(module != 0);
    if (module == 0) {
        return;
    }

    for (i = 0; i < sizeof(names)/sizeof(names[0]); ++i) {
        CHECK(GetProcAddress(module, names[i]) != 0);
    }

    FreeLibrary(module);
}


typedef int (__fastcall *RexHttpPostLinkFn)(
    void* self,
    void* ignored_edx,
    const char* link
);

static int write_u32_le(FILE* file, uint32_t value) {
    unsigned char data[4];

    data[0] = (unsigned char)(value & 0xFFu);
    data[1] = (unsigned char)((value >> 8) & 0xFFu);
    data[2] = (unsigned char)((value >> 16) & 0xFFu);
    data[3] = (unsigned char)((value >> 24) & 0xFFu);

    return fwrite(data, 1u, sizeof(data), file) == sizeof(data);
}

static int write_proxy_content_fixture(void) {
    static const unsigned char magic[8] = {
        'R', 'E', 'X', 'C', 'T', 'V', '2', 0
    };
    FILE* file = 0;
    int ok = 1;

    if (fopen_s(&file, "CampaignContentV2.dat", "wb") != 0 ||
        file == 0) {
        return 0;
    }

    ok = ok && fwrite(magic, 1u, sizeof(magic), file) == sizeof(magic);
    ok = ok && write_u32_le(file, 2u);
    ok = ok && write_u32_le(file, 2u);

    ok = ok && write_u32_le(file, 501u);
    ok = ok && write_u32_le(file, 1u);
    ok = ok && write_u32_le(file, 1u);
    ok = ok && write_u32_le(file, 9501u);
    ok = ok && write_u32_le(file, 4u);

    ok = ok && write_u32_le(file, 502u);
    ok = ok && write_u32_le(file, 0u);
    ok = ok && write_u32_le(file, 0u);
    ok = ok && write_u32_le(file, 0u);
    ok = ok && write_u32_le(file, 0u);

    ok = ok && write_u32_le(file, 1u);
    ok = ok && write_u32_le(file, 9501u);
    ok = ok && write_u32_le(file, 7u);

    ok = ok && write_u32_le(file, 0u);

    if (fclose(file) != 0) {
        ok = 0;
    }

    return ok;
}

static void cleanup_proxy_state(void) {
    remove("CampaignStateV1.dat");
    remove("CampaignStateV1.dat.tmp");
    remove("CampaignStateV1.dat.bak");
}

static void test_proxy_routes_new_gateway_to_rex_shim(void) {
    static const char http_name[] =
        "?HttpPostLink@IGPControl@IGPLib@@QAEXPBD@Z";
    HMODULE module;
    RexHttpPostLinkFn http_post;
    unsigned char garage[0x2D8] = {0};
    unsigned char selected[0xC4] = {0};
    void* selected_ptr = selected;
    uint32_t vehicle_id = 501u;
    int owned_before;
    int build_result;
    int owned_after;

    cleanup_proxy_state();
    CHECK(write_proxy_content_fixture() == 1);

    memcpy(garage + 0x2D4, &selected_ptr, sizeof(selected_ptr));
    memcpy(selected + 0xC0, &vehicle_id, sizeof(vehicle_id));

    module = LoadLibraryA("IGPLib_x86.dll");
    CHECK(module != 0);
    if (module == 0) {
        return;
    }

    http_post = (RexHttpPostLinkFn)GetProcAddress(
        module,
        http_name
    );
    CHECK(http_post != 0);

    if (http_post != 0) {
        owned_before = http_post(
            (void*)(uintptr_t)vehicle_id,
            0,
            (const char*)(uintptr_t)REX_IGP_GATE_OWNED
        );
        CHECK(owned_before == 0);

        build_result = http_post(
            garage,
            0,
            (const char*)(uintptr_t)REX_IGP_GATE_MONTAR
        );
        CHECK(build_result == 0);

        owned_after = http_post(
            (void*)(uintptr_t)vehicle_id,
            0,
            (const char*)(uintptr_t)REX_IGP_GATE_OWNED
        );
        CHECK(owned_after == 1);
    }

    FreeLibrary(module);
    remove("CampaignContentV2.dat");
    cleanup_proxy_state();
}

int main(void) {
    test_proxy_exposes_game_import_surface();
    test_proxy_routes_new_gateway_to_rex_shim();

    if (failures != 0) {
        printf("%d proxy assertion(s) failed.\n", failures);
        return 1;
    }

    printf("ReX IGP proxy tests passed.\n");
    return 0;
}
