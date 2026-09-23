#include "LocalEventRuntime.h"

#include <windows.h>
#include <cstdint>
#include <cwchar>
#include <cstdlib>
#include <cstring>

namespace {

constexpr std::uintptr_t kPreferredImageBase = 0x00400000u;
constexpr std::uintptr_t kBuildCarVA          = 0x00A87960u;
constexpr std::uintptr_t kGetSelectedCarIdVA  = 0x00D805F0u;
constexpr std::uintptr_t kBuildCarRVA         = kBuildCarVA - kPreferredImageBase;
constexpr std::uintptr_t kGetSelectedCarIdRVA = kGetSelectedCarIdVA - kPreferredImageBase;
constexpr UINT kUiRefreshMessage = WM_APP + 0x217;
constexpr bool kEnableOverlayUi = false; // R17.1: core first; overlay returns after runtime stability is proven.

using ConsumerFn = void (*)(const rextreme::local::LocalEvent&);
using GetSelectedCarIdFn = int (__thiscall*)(void* selected_car);

struct RuntimeState {
    CRITICAL_SECTION lock{};
    bool lock_ready = false;
    HINSTANCE module = nullptr;
    HMODULE ams = nullptr;
    HWND game_window = nullptr;
    HWND ui_window = nullptr;
    HWND local_build_button = nullptr;
    HANDLE thread = nullptr;
    DWORD thread_id = 0;
    volatile LONG stopping = 0;

    std::uint32_t revision = 0;
    std::uint32_t craft_count = 0;
    std::uint32_t sequence = 0;
    std::int32_t last_car_id = 0;
    void* last_garage = nullptr;
    wchar_t status[256]{};

    std::int32_t owned_cars[512]{};
    std::uint32_t owned_count = 0;

    ConsumerFn consumers[8]{};
    std::uint32_t consumer_count = 0;

    wchar_t state_path[MAX_PATH]{};
    wchar_t log_path[MAX_PATH]{};
};

RuntimeState g;
BYTE g_buildcar_original[5]{};
bool g_hook_installed = false;

void Lock() {
    if (g.lock_ready) EnterCriticalSection(&g.lock);
}

void Unlock() {
    if (g.lock_ready) LeaveCriticalSection(&g.lock);
}

void RequestUiRefresh() {
    if (g.ui_window) PostMessageW(g.ui_window, kUiRefreshMessage, 0, 0);
}

void CopyStatus(const wchar_t* text) {
    Lock();
    wcsncpy_s(g.status, text ? text : L"", _TRUNCATE);
    Unlock();
    RequestUiRefresh();
}

void EnsureLocalPaths() {
    wchar_t base[MAX_PATH]{};
    DWORD n = GetEnvironmentVariableW(L"LOCALAPPDATA", base, MAX_PATH);
    if (!n || n >= MAX_PATH) {
        GetCurrentDirectoryW(MAX_PATH, base);
    }

    wchar_t dir[MAX_PATH]{};
    swprintf_s(dir, L"%s\\ReXtremeLocal", base);
    CreateDirectoryW(dir, nullptr);
    swprintf_s(g.state_path, L"%s\\campaign.ini", dir);

    wchar_t cwd[MAX_PATH]{};
    GetCurrentDirectoryW(MAX_PATH, cwd);
    wchar_t trace[MAX_PATH]{};
    swprintf_s(trace, L"%s\\_TRACE_MONTAR", cwd);
    CreateDirectoryW(trace, nullptr);
    swprintf_s(g.log_path, L"%s\\R17-LOCAL-EVENT-RUNTIME.log", trace);
}

void Log(const wchar_t* text) {
    if (!g.log_path[0]) return;

    HANDLE h = CreateFileW(
        g.log_path,
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);

    if (h == INVALID_HANDLE_VALUE) return;

    SYSTEMTIME st{};
    GetLocalTime(&st);

    wchar_t line[1024]{};
    swprintf_s(
        line,
        L"[%04u-%02u-%02u %02u:%02u:%02u.%03u] %s\r\n",
        st.wYear,
        st.wMonth,
        st.wDay,
        st.wHour,
        st.wMinute,
        st.wSecond,
        st.wMilliseconds,
        text ? text : L"");

    DWORD bytes = 0;
    WriteFile(
        h,
        line,
        static_cast<DWORD>(wcslen(line) * sizeof(wchar_t)),
        &bytes,
        nullptr);

    CloseHandle(h);
}

bool OwnsCarUnlocked(std::int32_t car_id) {
    if (car_id <= 0) return false;

    for (std::uint32_t i = 0; i < g.owned_count; ++i) {
        if (g.owned_cars[i] == car_id) return true;
    }
    return false;
}

void AddOwnedCarUnlocked(std::int32_t car_id) {
    if (car_id <= 0 || OwnsCarUnlocked(car_id) || g.owned_count >= 512) return;
    g.owned_cars[g.owned_count++] = car_id;
}

void LoadStore() {
    EnsureLocalPaths();

    g.revision = GetPrivateProfileIntW(L"runtime", L"revision", 0, g.state_path);
    g.craft_count = GetPrivateProfileIntW(L"runtime", L"craft_count", 0, g.state_path);
    g.last_car_id = static_cast<std::int32_t>(
        GetPrivateProfileIntW(L"runtime", L"last_car_id", 0, g.state_path));

    wchar_t section[32768]{};
    DWORD count = GetPrivateProfileSectionW(
        L"owned_cars",
        section,
        static_cast<DWORD>(sizeof(section) / sizeof(section[0])),
        g.state_path);

    if (count > 0) {
        const wchar_t* p = section;

        while (*p && g.owned_count < 512) {
            const wchar_t* eq = wcschr(p, L'=');

            if (eq) {
                wchar_t key[32]{};
                size_t len = static_cast<size_t>(eq - p);

                if (len > 0 && len < 31) {
                    wcsncpy_s(key, p, len);
                    const int id = _wtoi(key);
                    const int enabled = _wtoi(eq + 1);

                    if (id > 0 && enabled != 0) {
                        AddOwnedCarUnlocked(id);
                    }
                }
            }

            p += wcslen(p) + 1;
        }
    }

    wcsncpy_s(g.status, L"Runtime local carregado. Aguardando garagem.", _TRUNCATE);
    Log(L"Local store loaded.");
}

void SaveStoreUnlocked() {
    wchar_t tmp[64]{};

    swprintf_s(tmp, L"%u", g.revision);
    WritePrivateProfileStringW(L"runtime", L"revision", tmp, g.state_path);

    swprintf_s(tmp, L"%u", g.craft_count);
    WritePrivateProfileStringW(L"runtime", L"craft_count", tmp, g.state_path);

    swprintf_s(tmp, L"%d", g.last_car_id);
    WritePrivateProfileStringW(L"runtime", L"last_car_id", tmp, g.state_path);

    WritePrivateProfileStringW(L"owned_cars", nullptr, nullptr, g.state_path);

    for (std::uint32_t i = 0; i < g.owned_count; ++i) {
        wchar_t key[32]{};
        swprintf_s(key, L"%d", g.owned_cars[i]);
        WritePrivateProfileStringW(L"owned_cars", key, L"1", g.state_path);
    }

    WritePrivateProfileStringW(nullptr, nullptr, nullptr, g.state_path);
}

void InventoryConsumer(const rextreme::local::LocalEvent& e) {
    if (e.type != rextreme::local::EventType::CraftRequested) return;

    Lock();
    ++g.craft_count;
    Unlock();
}

void ProfileConsumer(const rextreme::local::LocalEvent& e) {
    if (e.type != rextreme::local::EventType::CraftRequested) return;

    Lock();
    AddOwnedCarUnlocked(e.car_id);
    ++g.revision;
    Unlock();
}

void GarageConsumer(const rextreme::local::LocalEvent& e) {
    if (e.type != rextreme::local::EventType::CraftRequested) return;

    Lock();
    g.last_car_id = e.car_id;
    g.last_garage = e.garage;
    swprintf_s(g.status, L"Carro %d montado pelo runtime local.", e.car_id);
    Unlock();
}

void PersistenceConsumer(const rextreme::local::LocalEvent& e) {
    if (e.type != rextreme::local::EventType::CraftRequested) return;

    Lock();
    SaveStoreUnlocked();
    Unlock();

    Log(L"Craft transaction persisted locally.");
}

void RegisterConsumer(ConsumerFn fn) {
    if (g.consumer_count < 8) {
        g.consumers[g.consumer_count++] = fn;
    }
}

void Publish(rextreme::local::LocalEvent event) {
    ConsumerFn local[8]{};
    std::uint32_t n = 0;

    Lock();
    event.sequence = ++g.sequence;
    n = g.consumer_count;

    for (std::uint32_t i = 0; i < n; ++i) {
        local[i] = g.consumers[i];
    }
    Unlock();

    for (std::uint32_t i = 0; i < n; ++i) {
        if (local[i]) local[i](event);
    }

    RequestUiRefresh();
}

BOOL CALLBACK FindGameWindowProc(HWND hwnd, LPARAM param) {
    DWORD pid = 0;
    GetWindowThreadProcessId(hwnd, &pid);

    if (pid != GetCurrentProcessId() || !IsWindowVisible(hwnd)) {
        return TRUE;
    }

    if (GetWindow(hwnd, GW_OWNER) == nullptr) {
        *reinterpret_cast<HWND*>(param) = hwnd;
        return FALSE;
    }

    return TRUE;
}

HWND FindGameWindow() {
    HWND result = nullptr;
    EnumWindows(FindGameWindowProc, reinterpret_cast<LPARAM>(&result));
    return result;
}

int ResolveSelectedCarId(void* garage) {
    if (!garage || !g.ams) return 0;

    __try {
        auto* bytes = static_cast<BYTE*>(garage);
        void* holder = *reinterpret_cast<void**>(bytes + 0x2D4);

        if (!holder) return 0;

        void* selected = *reinterpret_cast<void**>(holder);

        if (!selected) return 0;

        auto fn = reinterpret_cast<GetSelectedCarIdFn>(
            reinterpret_cast<BYTE*>(g.ams) + kGetSelectedCarIdRVA);

        return fn(selected);
    }
    __except(EXCEPTION_EXECUTE_HANDLER) {
        Log(L"Selected car resolver raised an exception.");
        return 0;
    }
}

void HandleLocalCraft(void* garage) {
    if (!garage) {
        CopyStatus(L"Garagem ainda nao foi capturada.");
        return;
    }

    const int car_id = ResolveSelectedCarId(garage);

    if (car_id <= 0) {
        CopyStatus(L"Falha ao resolver car_id da selecao atual.");
        Log(L"BuildCar intercepted, but selected car id could not be resolved.");
        return;
    }

    {
        wchar_t line[256]{};
        swprintf_s(line, L"BuildCar intercepted locally. car_id=%d", car_id);
        Log(line);
    }

    rextreme::local::LocalEvent e{};
    e.type = rextreme::local::EventType::CraftRequested;
    e.car_id = car_id;
    e.garage = garage;

    Publish(e);
}

void __stdcall BuildCarDispatch(void* garage) {
    HandleLocalCraft(garage);
}

__declspec(naked) void BuildCarDetour() {
    __asm {
        pushfd
        pushad
        push ecx
        call BuildCarDispatch
        add esp, 4
        popad
        popfd
        ret
    }
}

bool InstallBuildCarHook() {
    if (!g.ams) return false;

    BYTE* target = reinterpret_cast<BYTE*>(g.ams) + kBuildCarRVA;
    const BYTE expected[5] = {0x55, 0x8B, 0xEC, 0x6A, 0xFF};

    if (memcmp(target, expected, sizeof(expected)) != 0) {
        Log(L"BuildCar prologue mismatch; hook not installed.");
        return false;
    }

    memcpy(g_buildcar_original, target, 5);

    DWORD oldProtect = 0;

    if (!VirtualProtect(target, 5, PAGE_EXECUTE_READWRITE, &oldProtect)) {
        Log(L"VirtualProtect failed while installing BuildCar hook.");
        return false;
    }

    const std::intptr_t rel =
        reinterpret_cast<BYTE*>(&BuildCarDetour) - (target + 5);

    target[0] = 0xE9;
    *reinterpret_cast<std::int32_t*>(target + 1) =
        static_cast<std::int32_t>(rel);

    FlushInstructionCache(GetCurrentProcess(), target, 5);

    DWORD ignored = 0;
    VirtualProtect(target, 5, oldProtect, &ignored);

    g_hook_installed = true;
    Log(L"GS_Garage::BuildCar replaced by LocalEventRuntime.");
    return true;
}

void RemoveBuildCarHook() {
    if (!g_hook_installed || !g.ams) return;

    BYTE* target = reinterpret_cast<BYTE*>(g.ams) + kBuildCarRVA;
    DWORD oldProtect = 0;

    if (VirtualProtect(target, 5, PAGE_EXECUTE_READWRITE, &oldProtect)) {
        memcpy(target, g_buildcar_original, 5);
        FlushInstructionCache(GetCurrentProcess(), target, 5);

        DWORD ignored = 0;
        VirtualProtect(target, 5, oldProtect, &ignored);
    }

    g_hook_installed = false;
}

void PositionUiWindow() {
    if (!g.ui_window) return;

    if (!g.game_window || !IsWindow(g.game_window)) {
        g.game_window = FindGameWindow();
    }

    if (!g.game_window) return;

    RECT r{};

    if (!GetWindowRect(g.game_window, &r)) return;

    const int width = 460;
    const int height = 145;
    const int x = r.right - width - 24;
    const int y = r.top + 54;

    SetWindowPos(
        g.ui_window,
        HWND_TOPMOST,
        x,
        y,
        width,
        height,
        SWP_NOACTIVATE | SWP_SHOWWINDOW);
}

void PaintUi(HWND hwnd) {
    PAINTSTRUCT ps{};
    HDC dc = BeginPaint(hwnd, &ps);

    RECT r{};
    GetClientRect(hwnd, &r);

    HBRUSH bg = CreateSolidBrush(RGB(12, 25, 37));
    FillRect(dc, &r, bg);
    DeleteObject(bg);

    SetBkMode(dc, TRANSPARENT);
    SetTextColor(dc, RGB(255, 191, 0));

    HFONT title = CreateFontW(
        24,
        0,
        0,
        0,
        FW_BOLD,
        FALSE,
        FALSE,
        FALSE,
        DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS,
        CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY,
        DEFAULT_PITCH,
        L"Segoe UI");

    HFONT old = static_cast<HFONT>(SelectObject(dc, title));
    TextOutW(dc, 18, 12, L"REXTREME LOCAL GARAGE", 21);
    SelectObject(dc, old);
    DeleteObject(title);

    rextreme::local::RuntimeSnapshot snap = rextreme::local::Snapshot();

    SetTextColor(dc, RGB(235, 240, 245));

    HFONT body = CreateFontW(
        18,
        0,
        0,
        0,
        FW_NORMAL,
        FALSE,
        FALSE,
        FALSE,
        DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS,
        CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY,
        DEFAULT_PITCH,
        L"Segoe UI");

    old = static_cast<HFONT>(SelectObject(dc, body));

    wchar_t meta[256]{};
    swprintf_s(
        meta,
        L"car_id: %d    crafts: %u    rev: %u",
        snap.last_car_id,
        snap.craft_count,
        snap.revision);

    TextOutW(dc, 18, 50, meta, static_cast<int>(wcslen(meta)));
    TextOutW(dc, 18, 78, snap.status, static_cast<int>(wcslen(snap.status)));

    SelectObject(dc, old);
    DeleteObject(body);

    EndPaint(hwnd, &ps);
}

LRESULT CALLBACK UiWndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
        case WM_CREATE:
            g.local_build_button = CreateWindowExW(
                0,
                L"BUTTON",
                L"MONTAR LOCAL",
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                300,
                105,
                140,
                30,
                hwnd,
                reinterpret_cast<HMENU>(1001),
                g.module,
                nullptr);

            SetTimer(hwnd, 1, 500, nullptr);
            return 0;

        case WM_COMMAND:
            if (LOWORD(wp) == 1001) {
                void* garage = nullptr;

                Lock();
                garage = g.last_garage;
                Unlock();

                HandleLocalCraft(garage);
                return 0;
            }
            break;

        case WM_TIMER:
            PositionUiWindow();
            return 0;

        case kUiRefreshMessage:
            InvalidateRect(hwnd, nullptr, FALSE);
            return 0;

        case WM_PAINT:
            PaintUi(hwnd);
            return 0;

        case WM_CLOSE:
            ShowWindow(hwnd, SW_HIDE);
            return 0;
    }

    return DefWindowProcW(hwnd, msg, wp, lp);
}

bool CreateUi() {
    WNDCLASSEXW wc{};
    wc.cbSize = sizeof(wc);
    wc.hInstance = g.module;
    wc.lpfnWndProc = UiWndProc;
    wc.lpszClassName = L"ReXtremeLocalGarageWindow";
    wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);

    RegisterClassExW(&wc);

    g.game_window = FindGameWindow();

    g.ui_window = CreateWindowExW(
        WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_LAYERED,
        wc.lpszClassName,
        L"ReXtreme Local Garage",
        WS_POPUP,
        CW_USEDEFAULT,
        CW_USEDEFAULT,
        460,
        145,
        g.game_window,
        nullptr,
        g.module,
        nullptr);

    if (!g.ui_window) {
        Log(L"Failed to create LocalGarageUI window.");
        return false;
    }

    SetLayeredWindowAttributes(g.ui_window, 0, 242, LWA_ALPHA);
    PositionUiWindow();
    ShowWindow(g.ui_window, SW_SHOWNOACTIVATE);
    UpdateWindow(g.ui_window);

    Log(L"LocalGarageUI created.");
    return true;
}

DWORD WINAPI RuntimeThread(LPVOID) {
    InitializeCriticalSection(&g.lock);
    g.lock_ready = true;
    g.ams = GetModuleHandleW(nullptr);

    // R17.1 is started only after the XAML IGP bridge is initialized.
    // Give the application bootstrap a short additional margin before touching AMS code.
    Sleep(1500);

    LoadStore();

    RegisterConsumer(InventoryConsumer);
    RegisterConsumer(ProfileConsumer);
    RegisterConsumer(GarageConsumer);
    RegisterConsumer(PersistenceConsumer);

    if (!InstallBuildCarHook()) {
        CopyStatus(L"R17 carregou, mas o hook BuildCar falhou.");
    } else {
        CopyStatus(L"R17 ativo. MONTAR agora usa o runtime local.");
    }

    if (kEnableOverlayUi) {
        CreateUi();
    } else {
        Log(L"R17.1 delayed core active; overlay intentionally disabled for stability test.");
    }

    MSG msg{};

    while (InterlockedCompareExchange(&g.stopping, 0, 0) == 0 &&
           GetMessageW(&msg, nullptr, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }

    RemoveBuildCarHook();

    if (g.ui_window && IsWindow(g.ui_window)) {
        DestroyWindow(g.ui_window);
    }

    g.ui_window = nullptr;

    if (g.lock_ready) {
        DeleteCriticalSection(&g.lock);
        g.lock_ready = false;
    }

    return 0;
}

} // namespace

namespace rextreme::local {

bool Start(HINSTANCE module) {
    if (g.thread) return true;

    g.module = module;
    InterlockedExchange(&g.stopping, 0);

    g.thread = CreateThread(
        nullptr,
        0,
        RuntimeThread,
        nullptr,
        0,
        &g.thread_id);

    return g.thread != nullptr;
}

void Stop() {
    InterlockedExchange(&g.stopping, 1);

    if (g.thread_id) {
        PostThreadMessageW(g.thread_id, WM_QUIT, 0, 0);
    }
}

bool IsCarOwned(std::int32_t car_id) {
    Lock();
    const bool result = OwnsCarUnlocked(car_id);
    Unlock();
    return result;
}

RuntimeSnapshot Snapshot() {
    RuntimeSnapshot out{};

    Lock();

    out.revision = g.revision;
    out.craft_count = g.craft_count;
    out.last_car_id = g.last_car_id;
    out.last_car_owned = OwnsCarUnlocked(g.last_car_id);
    wcsncpy_s(out.status, g.status, _TRUNCATE);

    Unlock();

    return out;
}

} // namespace rextreme::local

extern "C" __declspec(naked) void noop_ret(void) {
    __asm ret
}

extern "C" __declspec(naked) void noop_ret4(void) {
    __asm ret 4
}

extern "C" __declspec(naked) void ret_false(void) {
    __asm xor eax, eax
    __asm ret
}

extern "C" __declspec(naked) void ret_null(void) {
    __asm xor eax, eax
    __asm ret
}

extern "C" BOOL __cdecl ReXtremeStart() {
    return rextreme::local::Start(g.module) ? TRUE : FALSE;
}

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        // Passive loader entry: never create threads, UI or hooks while under loader lock.
        g.module = module;
        DisableThreadLibraryCalls(module);
    } else if (reason == DLL_PROCESS_DETACH) {
        rextreme::local::Stop();
    }

    return TRUE;
}
