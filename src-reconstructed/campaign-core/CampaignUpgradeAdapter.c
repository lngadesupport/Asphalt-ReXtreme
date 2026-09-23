#include <stdint.h>

#include "CampaignCore.h"
#include "CampaignUpgradeAdapter.h"

/*
  Read-only legacy presentation metadata.

  The object passed by the preserved GS_UpgradeCar UI has:

    +0x10 selected_entries_begin
    +0x14 selected_entries_end

  Each entry is 8 bytes and the first dword is the stable raw visual/content id
  historically serialized as up_id / bp_id / tu_id.

  Campaign prices, balances, levels and ownership are NOT read here.
*/

static uint32_t ReadU32(const void* base, uint32_t off) {
    const unsigned char* p = (const unsigned char*)base;
    return *(const uint32_t*)(p + off);
}

int __cdecl CampaignApplyLegacyUpgradeSelection(
    CampaignLegacyUpgradeSelectionArgs* args
) {
    CampaignUpgradeBatchArgs batch;
    const unsigned char* begin;
    const unsigned char* end;
    uint32_t bytes;
    uint32_t count;
    uint32_t i;
    volatile unsigned char* q;

    if (!args) return 0;

    args->status = 0;
    args->applied_count = 0;
    args->revision = 0;

    if (args->car_id <= 0 || !args->selection_object) return 0;

    begin = (const unsigned char*)(uintptr_t)ReadU32(args->selection_object, 0x10);
    end = (const unsigned char*)(uintptr_t)ReadU32(args->selection_object, 0x14);

    if (!begin || !end || end <= begin) return 0;

    bytes = (uint32_t)(end - begin);
    if ((bytes & 7u) != 0) return 0;

    count = bytes >> 3;
    if (count == 0 || count > CAMPAIGN_UPGRADE_BATCH_MAX) return 0;

    q = (volatile unsigned char*)&batch;
    for (i = 0; i < (uint32_t)sizeof(batch); ++i) q[i] = 0;

    batch.size = (uint32_t)sizeof(batch);
    batch.car_id = args->car_id;
    batch.count = count;

    for (i = 0; i < count; ++i) {
        int32_t raw_id = *(const int32_t*)(begin + i * 8u);
        if (raw_id <= 0) return 0;
        batch.ui_action_ids[i] = raw_id;
    }

    if (!CampaignApplyUpgradeBatch(&batch) || !batch.status) {
        args->revision = batch.revision;
        return 0;
    }

    args->status = 1;
    args->applied_count = batch.applied_count;
    args->revision = batch.revision;
    return 1;
}
