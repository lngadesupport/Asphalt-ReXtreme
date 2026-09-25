#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shobjidl.h>

#include "RexAmsHost.h"

static int RexAmsHost_BuildPath(
    wchar_t* output,
    size_t capacity,
    const wchar_t* directory,
    const wchar_t* name
) {
    int written;

    if (output == 0 ||
        capacity == 0u ||
        directory == 0 ||
        directory[0] == L'\0' ||
        name == 0 ||
        name[0] == L'\0') {
        return 0;
    }

    written = swprintf_s(
        output,
        capacity,
        L"%ls\\%ls",
        directory,
        name
    );

    return written > 0 &&
        (size_t)written < capacity;
}

static int RexAmsHost_FileExists(
    const wchar_t* directory,
    const wchar_t* name
) {
    wchar_t path[MAX_PATH];
    DWORD attributes;

    if (!RexAmsHost_BuildPath(
            path,
            MAX_PATH,
            directory,
            name)) {
        return 0;
    }

    attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES &&
        (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0u;
}

int RexAmsHost_ValidateLayout(
    const wchar_t* directory
) {
    if (directory == 0 || directory[0] == L'\0') {
        return REX_AMS_LAYOUT_INVALID_ARGUMENT;
    }

    if (!RexAmsHost_FileExists(
            directory,
            L"AppxManifest.xml")) {
        return REX_AMS_LAYOUT_MISSING_MANIFEST;
    }

    if (!RexAmsHost_FileExists(
            directory,
            L"AMS.Game.exe")) {
        return REX_AMS_LAYOUT_MISSING_GAME;
    }

    if (!RexAmsHost_FileExists(
            directory,
            L"RexCore.dll")) {
        return REX_AMS_LAYOUT_MISSING_CORE;
    }

    if (!RexAmsHost_FileExists(
            directory,
            L"RexGameShim.dll")) {
        return REX_AMS_LAYOUT_MISSING_SHIM;
    }

    if (!RexAmsHost_FileExists(
            directory,
            L"IGPLib_x86.dll")) {
        return REX_AMS_LAYOUT_MISSING_PROXY;
    }

    if (!RexAmsHost_FileExists(
            directory,
            L"CampaignContentV2.dat")) {
        return REX_AMS_LAYOUT_MISSING_CONTENT;
    }

    return REX_AMS_LAYOUT_OK;
}

const wchar_t* RexAmsHost_DefaultAumid(void) {
    return L"A278AB0D.AsphaltXtreme_h6adky7gbf63m!App";
}

#ifndef REX_AMS_HOST_NO_MAIN
static int RexAmsHost_GetExecutableDirectory(
    wchar_t* output,
    size_t capacity
) {
    DWORD length;
    wchar_t* slash;

    if (output == 0 || capacity < 2u) {
        return 0;
    }

    length = GetModuleFileNameW(
        0,
        output,
        (DWORD)capacity
    );
    if (length == 0u || length >= capacity) {
        return 0;
    }

    slash = wcsrchr(output, L'\\');
    if (slash == 0) {
        slash = wcsrchr(output, L'/');
    }
    if (slash == 0) {
        return 0;
    }

    *slash = L'\0';
    return 1;
}

static int RexAmsHost_ActivateGame(void) {
    IApplicationActivationManager* manager = 0;
    HRESULT init_result;
    HRESULT result;
    DWORD process_id = 0u;
    int should_uninitialize = 0;

    init_result = CoInitializeEx(
        0,
        COINIT_APARTMENTTHREADED
    );

    if (SUCCEEDED(init_result)) {
        should_uninitialize = 1;
    } else if (init_result != RPC_E_CHANGED_MODE) {
        return 20;
    }

    result = CoCreateInstance(
        CLSID_ApplicationActivationManager,
        0,
        CLSCTX_INPROC_SERVER,
        IID_PPV_ARGS(&manager)
    );

    if (FAILED(result) || manager == 0) {
        if (should_uninitialize) {
            CoUninitialize();
        }
        return 21;
    }

    result = manager->ActivateApplication(
        RexAmsHost_DefaultAumid(),
        0,
        AO_NONE,
        &process_id
    );

    manager->Release();

    if (should_uninitialize) {
        CoUninitialize();
    }

    if (FAILED(result) || process_id == 0u) {
        return 22;
    }

    return 0;
}

int WINAPI wWinMain(
    HINSTANCE instance,
    HINSTANCE previous,
    PWSTR command_line,
    int show
) {
    wchar_t directory[MAX_PATH];
    int layout_result;

    (void)instance;
    (void)previous;
    (void)command_line;
    (void)show;

    if (!RexAmsHost_GetExecutableDirectory(
            directory,
            MAX_PATH)) {
        MessageBoxW(
            0,
            L"Could not resolve the Campaign Edition directory.",
            L"Asphalt ReXtreme: Campaign Edition",
            MB_OK | MB_ICONERROR
        );
        return 10;
    }

    layout_result = RexAmsHost_ValidateLayout(directory);
    if (layout_result != REX_AMS_LAYOUT_OK) {
        wchar_t message[256];
        swprintf_s(
            message,
            256,
            L"Campaign Edition layout is incomplete (code %d).",
            layout_result
        );
        MessageBoxW(
            0,
            message,
            L"Asphalt ReXtreme: Campaign Edition",
            MB_OK | MB_ICONERROR
        );
        return 11;
    }

    return RexAmsHost_ActivateGame();
}
#endif
