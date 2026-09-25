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

int main(void) {
    test_proxy_exposes_game_import_surface();

    if (failures != 0) {
        printf("%d proxy assertion(s) failed.\n", failures);
        return 1;
    }

    printf("ReX IGP proxy tests passed.\n");
    return 0;
}
