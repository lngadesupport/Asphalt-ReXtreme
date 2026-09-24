#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static volatile LONG g_bridge_started = 0;

static void StartLocalRuntimeOnce(void) {
    HMODULE runtime;
    FARPROC start_proc;

    if (InterlockedCompareExchange(&g_bridge_started, 1, 0) != 0) {
        return;
    }

    runtime = LoadLibraryW(L"ReXtremeLocalRuntime.dll");
    if (!runtime) {
        InterlockedExchange(&g_bridge_started, 0);
        return;
    }

    start_proc = GetProcAddress(runtime, "ReXtremeStart");
    if (!start_proc) {
        FreeLibrary(runtime);
        InterlockedExchange(&g_bridge_started, 0);
        return;
    }

    ((BOOL (__cdecl *)(void))start_proc)();
}

/* cdecl on purpose: the original InitBridgeClass caller owns its argument cleanup. */
void __cdecl bridge_init(void) {
    StartLocalRuntimeOnce();
}

__declspec(naked) void noop_ret(void) {
    __asm ret
}

__declspec(naked) void noop_ret4(void) {
    __asm ret 4
}

__declspec(naked) void ret_false(void) {
    __asm xor eax, eax
    __asm ret
}

__declspec(naked) void ret_null(void) {
    __asm xor eax, eax
    __asm ret
}
