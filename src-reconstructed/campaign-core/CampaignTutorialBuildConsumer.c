#include <stdint.h>
#include "CampaignTutorialBuildConsumer.h"
#include "CampaignGarageFlow.h"
#include "CampaignEventBus.h"

extern void __cdecl CampaignInvokeGarageUi(void* widget);

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
    void* widget;
    void* pending_object;
    void* pending_control;

    if (!gs_garage) return 0;

    /*
      These are frontend presentation fields identified by the historical
      build/pending maps. Campaign Edition owns the business state; these
      pointers are only local UI latches that must be released after a local
      transaction finishes.
    */
    pending_object = *(void**)(gs + 0x3AC);
    pending_control = *(void**)(gs + 0x3B0);
    widget = *(void**)(gs + 0x35C);

    *(void**)(gs + 0x3AC) = 0;
    *(void**)(gs + 0x3B0) = 0;

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
        CampaignInvokeGarageUi(widget);
    }

    if (success) {
        CampaignGarageFlowFrontendCompleted(car_id, revision);
    } else {
        CampaignGarageFlowFail(car_id);
    }

    return 1;
}
