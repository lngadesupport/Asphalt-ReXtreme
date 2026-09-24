#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignTutorialBuildConsumer.h"
#include "CampaignGarageFlow.h"
#include "CampaignEventBus.h"
#include "CampaignGarageUiTrace.h"

#define CAMPAIGN_AMS_IMAGE_BASE 0x00400000u
#define CAMPAIGN_GBBW_READY_UI_RVA (0x00974480u - CAMPAIGN_AMS_IMAGE_BASE)
#define CAMPAIGN_GBBW_SECONDARY_UPDATE_RVA (0x00975A50u - CAMPAIGN_AMS_IMAGE_BASE)

__declspec(naked) static void __cdecl CampaignCallFrontendThis0(
    void* target,
    void* object
) {
    __asm {
        mov eax, dword ptr [esp+4]
        mov ecx, dword ptr [esp+8]
        test eax, eax
        jz call_done
        test ecx, ecx
        jz call_done
        call eax
call_done:
        ret
    }
}

static void CampaignRefreshGarageBottomBar(void* widget) {
    HMODULE ams;
    unsigned char* base;

    if (!widget) return;

    ams = GetModuleHandleW(0);
    if (!ams) return;

    base = (unsigned char*)ams;

    /*
      Both targets are frontend-only GarageBottomBarWidget update routines
      identified by the historical Phase56/66 maps.  They read the already
      committed local UI state; they do not submit CraftCar/network work.
    */
    CampaignCallFrontendThis0(
        (void*)(base + CAMPAIGN_GBBW_SECONDARY_UPDATE_RVA),
        widget
    );
    CampaignCallFrontendThis0(
        (void*)(base + CAMPAIGN_GBBW_READY_UI_RVA),
        widget
    );
}

static void ZeroBytes(void* p, uint32_t count) {
    volatile unsigned char* q = (volatile unsigned char*)p;
    uint32_t i;
    for (i = 0; i < count; ++i) q[i] = 0;
}

int __cdecl CampaignTutorialBuildComplete(
    void* gs_garage,
    int32_t car_id,
    int32_t success,
    uint32_t revision,
    CampaignTutorialBuildUiResult* out
) {
    unsigned char* gs = (unsigned char*)gs_garage;
    unsigned char* gbbw;
    void* widget;
    void* pending_object;
    void* pending_control;
    void* build_signal_object = 0;
    void* build_signal_control = 0;

    if (!gs_garage) return 0;

    /*
      Frontend-only state identified by the Phase71-79 garage maps.

      GS_Garage:
        +0x35C -> GarageBottomBarWidget
        +0x3AC/+0x3B0 -> local pending build presentation state

      GarageBottomBarWidget:
        +0x44/+0x48 -> build-button signal/shared state

      Campaign Edition does not complete a fake request. It directly releases
      the presentation latches after the local transaction has committed.
    */
    pending_object = *(void**)(gs + 0x3AC);
    pending_control = *(void**)(gs + 0x3B0);
    widget = *(void**)(gs + 0x35C);

    CampaignGarageUiTraceWrite(20, gs_garage, widget);

    *(void**)(gs + 0x3AC) = 0;
    *(void**)(gs + 0x3B0) = 0;

    gbbw = (unsigned char*)widget;
    if (gbbw) {
        build_signal_object = *(void**)(gbbw + 0x44);
        build_signal_control = *(void**)(gbbw + 0x48);

        /*
          Do not call the legacy signal/callback chain.  Detach the local
          frontend latch from the completed MONTAR action instead.
          Any referenced legacy connection may leak until this widget is
          destroyed, but it can no longer keep the operation pending.
        */
        *(void**)(gbbw + 0x44) = 0;
        *(void**)(gbbw + 0x48) = 0;
    }

    CampaignGarageUiTraceWrite(21, gs_garage, widget);

    if (out && out->size >= (uint32_t)sizeof(*out)) {
        ZeroBytes(out, (uint32_t)sizeof(*out));
        out->size = (uint32_t)sizeof(*out);
        out->car_id = car_id;
        out->success = success ? 1 : 0;
        out->revision = revision;
        out->pending_object_before = (uint32_t)(uintptr_t)pending_object;
        out->pending_control_before = (uint32_t)(uintptr_t)pending_control;
        out->widget = (uint32_t)(uintptr_t)widget;
    }

    if (widget) {
        CampaignRefreshGarageBottomBar(widget);
    }

    CampaignGarageUiTraceWrite(22, gs_garage, widget);

    if (success) {
        CampaignGarageFlowFrontendCompleted(car_id, revision);
    } else {
        CampaignGarageFlowFail(car_id);
    }

    return 1;
}
