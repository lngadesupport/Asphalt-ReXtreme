#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include "RexAmsHost.h"

int RexAmsHost_ValidateLayout(
    const wchar_t* directory
) {
    (void)directory;
    return REX_AMS_LAYOUT_INVALID_ARGUMENT;
}

const wchar_t* RexAmsHost_DefaultAumid(void) {
    return L"A278AB0D.AsphaltXtreme_h6adky7gbf63m!App";
}

#ifndef REX_AMS_HOST_NO_MAIN
int WINAPI wWinMain(
    HINSTANCE instance,
    HINSTANCE previous,
    PWSTR command_line,
    int show
) {
    (void)instance;
    (void)previous;
    (void)command_line;
    (void)show;
    return 1;
}
#endif
