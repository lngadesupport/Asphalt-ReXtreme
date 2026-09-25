#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

#include "RexAmsHost.h"

static int failures = 0;

#define CHECK(expr) do { \
    if (!(expr)) { \
        wprintf(L"FAIL %S:%d: %S\n", __FILE__, __LINE__, #expr); \
        failures += 1; \
    } \
} while (0)

static int touch_file(
    const wchar_t* directory,
    const wchar_t* name
) {
    wchar_t path[MAX_PATH];
    HANDLE file;

    if (swprintf_s(
            path,
            MAX_PATH,
            L"%ls\\%ls",
            directory,
            name) < 0) {
        return 0;
    }

    file = CreateFileW(
        path,
        GENERIC_WRITE,
        0,
        0,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        0
    );

    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }

    CloseHandle(file);
    return 1;
}

static void remove_file(
    const wchar_t* directory,
    const wchar_t* name
) {
    wchar_t path[MAX_PATH];

    if (swprintf_s(
            path,
            MAX_PATH,
            L"%ls\\%ls",
            directory,
            name) >= 0) {
        DeleteFileW(path);
    }
}

static void test_layout_contract(void) {
    static const wchar_t* names[] = {
        L"AppxManifest.xml",
        L"AMS.Game.exe",
        L"RexCore.dll",
        L"RexGameShim.dll",
        L"IGPLib_x86.dll",
        L"CampaignContentV2.dat"
    };
    wchar_t temp[MAX_PATH];
    wchar_t directory[MAX_PATH];
    DWORD length;
    size_t i;

    length = GetTempPathW(MAX_PATH, temp);
    CHECK(length > 0u && length < MAX_PATH);
    if (length == 0u || length >= MAX_PATH) {
        return;
    }

    CHECK(swprintf_s(
        directory,
        MAX_PATH,
        L"%lsRexAmsHostTest-%lu",
        temp,
        GetCurrentProcessId()) >= 0);

    RemoveDirectoryW(directory);
    CHECK(CreateDirectoryW(directory, 0) != 0);

    CHECK(
        RexAmsHost_ValidateLayout(directory) ==
        REX_AMS_LAYOUT_MISSING_MANIFEST
    );

    for (i = 0; i < sizeof(names) / sizeof(names[0]); ++i) {
        CHECK(touch_file(directory, names[i]) == 1);
    }

    CHECK(
        RexAmsHost_ValidateLayout(directory) ==
        REX_AMS_LAYOUT_OK
    );

    remove_file(directory, L"RexCore.dll");
    CHECK(
        RexAmsHost_ValidateLayout(directory) ==
        REX_AMS_LAYOUT_MISSING_CORE
    );

    for (i = 0; i < sizeof(names) / sizeof(names[0]); ++i) {
        remove_file(directory, names[i]);
    }
    RemoveDirectoryW(directory);
}

static void test_default_aumid(void) {
    CHECK(wcscmp(
        RexAmsHost_DefaultAumid(),
        L"A278AB0D.AsphaltXtreme_h6adky7gbf63m!App"
    ) == 0);
}

int main(void) {
    test_layout_contract();
    test_default_aumid();

    if (failures != 0) {
        printf("%d AMS host assertion(s) failed.\n", failures);
        return 1;
    }

    printf("ReX AMS host tests passed.\n");
    return 0;
}
