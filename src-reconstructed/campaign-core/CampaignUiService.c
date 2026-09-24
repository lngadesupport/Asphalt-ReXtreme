#include <stdint.h>
#include "CampaignUiService.h"
#include "CampaignEventBus.h"

int __cdecl CampaignUiShouldSuppressLegacyKind(uint32_t kind) {
    switch (kind) {
    case CAMPAIGN_UI_CONNECTION_ERROR:
    case CAMPAIGN_UI_RETRY_CONNECTION:
    case CAMPAIGN_UI_CLOUD_SYNC:
    case CAMPAIGN_UI_ONLINE_REQUIRED:
        return 1;
    default:
        return 0;
    }
}

int __cdecl CampaignUiSubmit(CampaignUiRequest* request) {
    CampaignEvent ev;

    if (!request || request->size < (uint32_t)sizeof(CampaignUiRequest)) return 0;

    request->status = 0;

    if (CampaignUiShouldSuppressLegacyKind(request->kind)) {
        request->status = 1;
        return 1;
    }

    ev.size = (uint32_t)sizeof(ev);
    ev.type = CAMPAIGN_EVENT_UI_NOTICE;
    ev.sequence = 0;
    ev.a = (int32_t)request->kind;
    ev.b = request->message_id;
    ev.c = request->a;
    ev.d = request->b;

    if (!CampaignEventPublish(&ev)) return 0;

    request->status = 1;
    return 1;
}
