#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignFrontendBridge.h"
#include "CampaignCore.h"
#include "CampaignServices.h"
#include "CampaignEventBus.h"
#include "CampaignUiService.h"
#include "CampaignOnlinePolicy.h"
#include "CampaignStartupService.h"
#include "CampaignGarageFlow.h"

static void ZeroBytes(void* p, uint32_t count) {
    volatile unsigned char* q = (volatile unsigned char*)p;
    uint32_t i;
    for (i = 0; i < count; ++i) q[i] = 0;
}

static void PublishSimple(uint32_t type, int32_t a, int32_t b) {
    CampaignEvent ev;
    ZeroBytes(&ev, (uint32_t)sizeof(ev));
    ev.size = (uint32_t)sizeof(ev);
    ev.type = type;
    ev.a = a;
    ev.b = b;
    CampaignEventPublish(&ev);
}

int __cdecl CampaignFrontendSubmit(CampaignFrontendRequest* r) {
    if (!r || r->size < (uint32_t)sizeof(CampaignFrontendRequest)) return 0;

    r->status = 0;
    r->out0 = 0;
    r->out1 = 0;
    r->out2 = 0;
    r->revision = 0;

    switch (r->type) {
    case CAMPAIGN_FRONTEND_BOOT:
        if (!CampaignStartupBegin()) return 0;
        r->status = 1;
        return 1;

    case CAMPAIGN_FRONTEND_PROFILE_READY:
        PublishSimple(CAMPAIGN_EVENT_PROFILE_READY, 0, 0);
        r->status = 1;
        return 1;

    case CAMPAIGN_FRONTEND_ENTER_LOBBY:
        if (!CampaignStartupEnterLobby()) return 0;
        r->status = 1;
        return 1;

    case CAMPAIGN_FRONTEND_BUILD_CAR:
        {
            CampaignGarageResult out;
            ZeroBytes(&out, (uint32_t)sizeof(out));
            out.size = (uint32_t)sizeof(out);
            if (!CampaignServiceGarageAcquire(r->a, &out)) return 0;
            r->status = 1;
            r->out0 = out.owned;
            r->out1 = out.balance_before;
            r->out2 = out.balance_after;
            r->revision = out.revision;
            return 1;
        }

    case CAMPAIGN_FRONTEND_QUERY_OWNERSHIP:
        {
            CampaignGarageResult out;
            ZeroBytes(&out, (uint32_t)sizeof(out));
            out.size = (uint32_t)sizeof(out);
            if (!CampaignServiceGarageIsOwned(r->a, &out)) return 0;
            r->status = 1;
            r->out0 = out.owned;
            r->revision = out.revision;
            return 1;
        }

    case CAMPAIGN_FRONTEND_START_EVENT:
        {
            uint32_t session_id = 0;
            if (!CampaignServiceCareerStart(r->a, r->b, &session_id)) return 0;
            r->status = 1;
            r->out0 = (int32_t)session_id;
            return 1;
        }

    case CAMPAIGN_FRONTEND_FINISH_EVENT:
        {
            CampaignRaceResult out;
            ZeroBytes(&out, (uint32_t)sizeof(out));
            out.size = (uint32_t)sizeof(out);
            if (!CampaignServiceCareerFinish((uint32_t)r->a, r->b, r->c, r->d, &out)) return 0;
            r->status = 1;
            r->out0 = out.credits_awarded;
            r->out1 = out.premium_awarded;
            r->out2 = out.stars_awarded;
            r->revision = out.revision;
            return 1;
        }

    case CAMPAIGN_FRONTEND_APPLY_UPGRADE:
        {
            CampaignUpgradeResult out;
            ZeroBytes(&out, (uint32_t)sizeof(out));
            out.size = (uint32_t)sizeof(out);
            if (!CampaignServiceUpgradeApply(r->a, r->b, &out)) return 0;
            r->status = 1;
            r->out0 = out.target_level;
            r->out1 = out.balance_before;
            r->out2 = out.balance_after;
            r->revision = out.revision;
            return 1;
        }

    case CAMPAIGN_FRONTEND_PURCHASE_OFFER:
        {
            CampaignStoreResult out;
            ZeroBytes(&out, (uint32_t)sizeof(out));
            out.size = (uint32_t)sizeof(out);
            if (!CampaignServiceStorePurchase(r->a, &out)) return 0;
            r->status = 1;
            r->out0 = out.item_id;
            r->out1 = out.balance_before;
            r->out2 = out.balance_after;
            r->revision = out.revision;
            return 1;
        }

    case CAMPAIGN_FRONTEND_OPEN_GARAGE:
    case CAMPAIGN_FRONTEND_OPEN_STORE:
    case CAMPAIGN_FRONTEND_UI_ACK:
        r->status = 1;
        return 1;

    default:
        return 0;
    }
}

int __cdecl CampaignFrontendPoll(CampaignEvent* event) {
    return CampaignEventPoll(event);
}


int __cdecl CampaignFrontendBoot(void) {
    CampaignFrontendRequest request;
    ZeroBytes(&request, (uint32_t)sizeof(request));
    request.size = (uint32_t)sizeof(request);
    request.type = CAMPAIGN_FRONTEND_BOOT;
    return CampaignFrontendSubmit(&request);
}

int __cdecl CampaignFrontendLobbyReady(void) {
    CampaignFrontendRequest request;
    ZeroBytes(&request, (uint32_t)sizeof(request));
    request.size = (uint32_t)sizeof(request);
    request.type = CAMPAIGN_FRONTEND_ENTER_LOBBY;
    return CampaignFrontendSubmit(&request);
}


#define CAMPAIGN_AMS_CRAFT_UI_COMPLETION_RVA 0x006A4D00u

/*
  x86 bridge for the preserved frontend callback.

  target callback ABI, proven by the Phase48 disassembly:
      ECX = observer
      push auxiliary
      push unused
      push status
      call target
      target returns with ret 0x0C

  This helper itself is cdecl; its own three arguments are cleaned by the
  C caller after this naked function returns.
*/
__declspec(naked) static void __cdecl CampaignCallCraftUiCompletion(
    void* target,
    void* observer,
    int32_t status
) {
    __asm {
        mov eax, dword ptr [esp+4]
        mov ecx, dword ptr [esp+8]
        mov edx, dword ptr [esp+0Ch]
        push 0
        push 0
        push edx
        call eax
        ret
    }
}

static void CampaignFrontendCompleteGarageBuild(void* gs_garage, int32_t status) {
    HMODULE ams;
    void* target;
    void* observer;

    if (!gs_garage) return;

    ams = GetModuleHandleW(0);
    if (!ams) return;

    /*
      Frontend-only adapter proven by the historical Phase48 map:
      observer = GS_Garage + 0x298
      status   = 0 on local success
      callback = AMS + RVA 0x006A4D00

      This callback is retained only for presentation/tutorial completion:
      it clears the frontend pending state and releases the build spinner.
      It is not a business/backend authority.
    */
    observer = (void*)((unsigned char*)gs_garage + 0x298);
    target = (void*)((unsigned char*)ams + CAMPAIGN_AMS_CRAFT_UI_COMPLETION_RVA);
    CampaignCallCraftUiCompletion(target, observer, status);
}


static WCHAR g_trace_local_app_data[1024];
static WCHAR g_trace_family[256];
static WCHAR g_trace_path[1400];

typedef LONG (WINAPI *CampaignGetCurrentPackageFamilyNameFn)(
    UINT32* packageFamilyNameLength,
    PWSTR packageFamilyName
);

typedef struct CampaignGarageTraceRecord {
    uint32_t magic;
    uint32_t version;
    uint32_t step;
    uint32_t gs_garage;
    uint32_t holder;
    uint32_t selected;
    int32_t car_id;
    int32_t acquire_ok;
    int32_t owned;
    int32_t callback_status;
    uint32_t revision;
} CampaignGarageTraceRecord;

#define CAMPAIGN_GARAGE_TRACE_MAGIC 0x47545852u /* RXTG */

static void CampaignGarageTraceWrite(
    uint32_t step,
    void* gs_garage,
    void* holder,
    void* selected,
    int32_t car_id,
    int32_t acquire_ok,
    int32_t owned,
    int32_t callback_status,
    uint32_t revision
) {
    HANDLE f;
    DWORD n;
    CampaignGarageTraceRecord r;
    DWORD i;
    UINT32 family_len = 256;
    HMODULE kernel32;
    CampaignGetCurrentPackageFamilyNameFn get_family;
    const WCHAR packages[] = L"\\Packages\\";
    const WCHAR suffix[] = L"\\LocalState\\CampaignEdition\\GarageTrace.bin";

    kernel32 = GetModuleHandleW(L"kernel32.dll");
    if (!kernel32) return;

    get_family = (CampaignGetCurrentPackageFamilyNameFn)
        GetProcAddress(kernel32, "GetCurrentPackageFamilyName");
    if (!get_family) return;

    if (!GetEnvironmentVariableW(
            L"LOCALAPPDATA",
            g_trace_local_app_data,
            1024)) return;

    if (get_family(&family_len, g_trace_family) != ERROR_SUCCESS) return;

    for (
        i = 0;
        g_trace_local_app_data[i] && i < 1399;
        ++i
    ) {
        g_trace_path[i] = g_trace_local_app_data[i];
    }
    if (i >= 1399) return;

    {
        DWORD j = 0;
        while (packages[j] && i < 1399) {
            g_trace_path[i++] = packages[j++];
        }

        j = 0;
        while (g_trace_family[j] && i < 1399) {
            g_trace_path[i++] = g_trace_family[j++];
        }

        j = 0;
        while (suffix[j] && i < 1399) {
            g_trace_path[i++] = suffix[j++];
        }

        g_trace_path[i] = 0;
    }

    r.magic = CAMPAIGN_GARAGE_TRACE_MAGIC;
    r.version = 1;
    r.step = step;
    r.gs_garage = (uint32_t)(uintptr_t)gs_garage;
    r.holder = (uint32_t)(uintptr_t)holder;
    r.selected = (uint32_t)(uintptr_t)selected;
    r.car_id = car_id;
    r.acquire_ok = acquire_ok;
    r.owned = owned;
    r.callback_status = callback_status;
    r.revision = revision;

    f = CreateFileW(
        g_trace_path,
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        0,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        0
    );
    if (f == INVALID_HANDLE_VALUE) return;
    SetFilePointer(f, 0, 0, FILE_END);
    WriteFile(f, &r, (DWORD)sizeof(r), &n, 0);
    CloseHandle(f);
}

static int32_t CampaignFrontendSelectedCarIdDetailed(
    void* gs_garage,
    void** holder_out,
    void** selected_out
) {
    unsigned char* gs = (unsigned char*)gs_garage;
    void* holder = 0;
    void* selected = 0;

    if (holder_out) *holder_out = 0;
    if (selected_out) *selected_out = 0;
    if (!gs) return 0;

    holder = *(void**)(gs + 0x2D4);
    if (holder_out) *holder_out = holder;
    if (!holder) return 0;

    selected = *(void**)holder;
    if (selected_out) *selected_out = selected;
    if (!selected) return 0;

    return *(int32_t*)((unsigned char*)selected + 0xC0);
}

static int32_t CampaignFrontendSelectedCarId(void* gs_garage) {
    unsigned char* gs = (unsigned char*)gs_garage;
    void* holder;
    void* selected;

    if (!gs) return 0;
    holder = *(void**)(gs + 0x2D4);
    if (!holder) return 0;
    selected = *(void**)holder;
    if (!selected) return 0;
    return *(int32_t*)((unsigned char*)selected + 0xC0);
}

int __cdecl CampaignFrontendGarageBuild(void* gs_garage) {
    CampaignGarageResult out;
    int32_t car_id;
    int acquire_ok;
    void* holder = 0;
    void* selected = 0;

    car_id = CampaignFrontendSelectedCarIdDetailed(
        gs_garage,
        &holder,
        &selected
    );

    CampaignGarageTraceWrite(
        1, gs_garage, holder, selected, car_id, 0, 0, -1, 0
    );

    /*
      Critical invariant:
      once the frontend entered MONTAR, every exit path must complete the
      preserved frontend operation. Otherwise the tutorial spinner can stay
      latched forever.
    */
    if (car_id <= 0) {
        CampaignGarageFlowFail(car_id);
        CampaignFrontendCompleteGarageBuild(gs_garage, 1);
        CampaignGarageTraceWrite(
            2, gs_garage, holder, selected, car_id, 0, 0, 1, 0
        );
        return 0;
    }

    CampaignGarageFlowBegin(car_id);

    ZeroBytes(&out, (uint32_t)sizeof(out));
    out.size = (uint32_t)sizeof(out);

    acquire_ok = CampaignServiceGarageAcquire(car_id, &out);
    CampaignGarageTraceWrite(
        3, gs_garage, holder, selected, car_id,
        acquire_ok, out.owned, -1, out.revision
    );

    if (!acquire_ok || !out.owned) {
        CampaignGarageFlowFail(car_id);
        CampaignFrontendCompleteGarageBuild(gs_garage, 1);
        CampaignGarageTraceWrite(
            4, gs_garage, holder, selected, car_id,
            acquire_ok, out.owned, 1, out.revision
        );
        return 0;
    }

    CampaignGarageFlowCommit(car_id, out.revision);

    CampaignFrontendCompleteGarageBuild(gs_garage, 0);
    CampaignGarageTraceWrite(
        5, gs_garage, holder, selected, car_id,
        1, 1, 0, out.revision
    );

    CampaignGarageFlowFrontendCompleted(car_id, out.revision);
    return 1;
}



int __cdecl CampaignFrontendIsOwned(int32_t car_id) {
    CampaignGarageResult out;

    if (car_id <= 0) return 0;

    ZeroBytes(&out, (uint32_t)sizeof(out));
    out.size = (uint32_t)sizeof(out);
    if (!CampaignServiceGarageIsOwned(car_id, &out)) return 0;
    return out.owned ? 1 : 0;
}
