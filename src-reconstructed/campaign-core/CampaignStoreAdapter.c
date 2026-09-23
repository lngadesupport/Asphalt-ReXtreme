#include <stdint.h>

#include "CampaignCore.h"
#include "CampaignStoreAdapter.h"

/*
  Verified read-only legacy metadata path.

  The object passed to the old OnlinePurchaseRequest::Start is the same
  PurchaseRequestContext shared by request+0x50/+0x54.

  Legacy serializer evidence:
    PurchaseRequestContext +0x08 -> shared item object
    item object +0x0C           -> zero-terminated item key used after "item="

  No old price, balance, result or backend state is read.
*/

#define CAMPAIGN_STORE_KEY_MAX 512u

static void ZeroBytes(void* p, uint32_t count) {
    volatile unsigned char* q = (volatile unsigned char*)p;
    uint32_t i;
    for (i = 0; i < count; ++i) q[i] = 0;
}

static const char* LegacyStoreItemKey(const void* purchase_context) {
    const unsigned char* context;
    const unsigned char* item_object;
    const char* key;

    if (!purchase_context) return 0;
    context = (const unsigned char*)purchase_context;

    item_object = *(const unsigned char* const*)(context + 0x08);
    if (!item_object) return 0;

    key = *(const char* const*)(item_object + 0x0C);
    if (!key || !key[0]) return 0;
    return key;
}

uint32_t __cdecl CampaignStoreKeyHash(const char* key) {
    uint32_t h = 2166136261u;
    uint32_t i = 0;
    unsigned char ch;

    if (!key || !key[0]) return 0;

    while (i < CAMPAIGN_STORE_KEY_MAX) {
        ch = (unsigned char)key[i++];
        if (!ch) {
            h &= 0x7FFFFFFFu;
            return h ? h : 1u;
        }
        h ^= (uint32_t)ch;
        h *= 16777619u;
    }

    /* Unbounded/malformed legacy key: fail closed. */
    return 0;
}

int __cdecl CampaignPurchaseLegacyStore(CampaignLegacyStoreArgs* args) {
    CampaignCommand cmd;
    const char* key;
    uint32_t offer_id;

    if (!args || !args->purchase_context) return 0;

    args->status = 0;
    args->offer_id = 0;
    args->item_id = 0;
    args->balance_before = 0;
    args->balance_after = 0;
    args->revision = 0;

    key = LegacyStoreItemKey(args->purchase_context);
    offer_id = CampaignStoreKeyHash(key);
    if (!offer_id) return 0;

    ZeroBytes(&cmd, (uint32_t)sizeof(cmd));
    cmd.size = (uint32_t)sizeof(cmd);
    cmd.op = CAMPAIGN_OP_PURCHASE_OFFER;
    cmd.a = (int32_t)offer_id;

    if (!CampaignExecuteCommand(&cmd) || !cmd.status) {
        args->offer_id = (int32_t)offer_id;
        args->revision = cmd.revision;
        return 0;
    }

    args->status = 1;
    args->offer_id = (int32_t)offer_id;
    args->item_id = cmd.out0;
    args->balance_before = cmd.out1;
    args->balance_after = cmd.out2;
    args->revision = cmd.revision;
    return 1;
}
