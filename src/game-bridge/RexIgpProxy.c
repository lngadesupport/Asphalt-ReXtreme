#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "RexIgpProxy.h"

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved) {
    (void)module;
    (void)reason;
    (void)reserved;
    return TRUE;
}
