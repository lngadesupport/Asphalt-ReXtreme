#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>

#include "RexIgpProxy.h"

static int g_proxy_instance;

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved) {
    (void)module;
    (void)reason;
    (void)reserved;
    return TRUE;
}

void __fastcall RexIGP_AddIGPComponent(
    void* self,
    void* ignored_edx,
    const char* component
) {
    (void)self;
    (void)ignored_edx;
    (void)component;
}

void __cdecl RexIGP_DestroyIGP(void) {
}

void* __cdecl RexIGP_GetInstance(void) {
    return &g_proxy_instance;
}

int __fastcall RexIGP_HttpPostLink(
    void* self,
    void* ignored_edx,
    const char* link
) {
    (void)self;
    (void)ignored_edx;
    (void)link;
    return 0;
}

void __cdecl RexIGP_Init(const void* params) {
    (void)params;
}

void __cdecl RexIGP_InitBridgeCallbacks(void) {
}

void __cdecl RexIGP_InitBridgeClass(void* panel) {
    (void)panel;
}

int __cdecl RexIGP_IsOnScreenFreemium(void) {
    return 0;
}

void __fastcall RexIGP_PauseIGP(
    void* self,
    void* ignored_edx
) {
    (void)self;
    (void)ignored_edx;
}

void __fastcall RexIGP_ResumeIGP(
    void* self,
    void* ignored_edx
) {
    (void)self;
    (void)ignored_edx;
}

void __cdecl RexIGP_SetGender(const char* value) {
    (void)value;
}

void __fastcall RexIGP_SetIGPLanguage(
    void* self,
    void* ignored_edx,
    const char* value
) {
    (void)self;
    (void)ignored_edx;
    (void)value;
}

void __cdecl RexIGP_SetUserAge(const char* value) {
    (void)value;
}

void __fastcall RexIGP_ShowIGP(
    void* self,
    void* ignored_edx,
    int show
) {
    (void)self;
    (void)ignored_edx;
    (void)show;
}
