#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>

#include "CampaignCore.h"
#include "CampaignCareerAdapter.h"

/*
  Verified legacy presentation/request layouts for this x86 build.

  PreCareerEventRequest:
    +0x40 event_id
    +0x44 car_id

  PostCareerEventRequest:
    +0x40 car_id
    +0x64 event_id
    +0x68 star1 byte
    +0x69 star2 byte
    +0x6A star3 byte
    +0x78 obfuscated position_in_race
    +0x7C obfuscated race_time

  These offsets are adapter metadata only. Campaign Core remains the
  authority for progression, rewards and persistence.
*/

#define AMS_OBFUSCATION_KEY_RVA 0x0153A1C8u

static int32_t ReadI32(const void* base, uint32_t off) {
    const unsigned char* p = (const unsigned char*)base;
    return *(const int32_t*)(p + off);
}

static uint8_t ReadU8(const void* base, uint32_t off) {
    const unsigned char* p = (const unsigned char*)base;
    return *(const uint8_t*)(p + off);
}

static int32_t DecodeAddressXorI32(const void* base, uint32_t off) {
    HMODULE ams;
    const unsigned char* field;
    uint32_t encoded;
    uint32_t key;

    if (!base) return 0;

    ams = GetModuleHandleW(0);
    if (!ams) return 0;

    field = (const unsigned char*)base + off;
    encoded = *(const uint32_t*)field;
    key = *(const uint32_t*)((const unsigned char*)ams + AMS_OBFUSCATION_KEY_RVA);

    return (int32_t)(encoded ^ (uint32_t)(uintptr_t)field ^ key);
}

int __cdecl CampaignBeginCareerFromPreRequest(void* pre_request) {
    CampaignCommand cmd;
    int32_t event_id;
    int32_t car_id;

    if (!pre_request) return 0;

    event_id = ReadI32(pre_request, 0x40);
    car_id = ReadI32(pre_request, 0x44);
    if (event_id <= 0) return 0;

    ZeroMemory(&cmd, sizeof(cmd));
    cmd.size = sizeof(cmd);
    cmd.op = CAMPAIGN_OP_BEGIN_EVENT_RACE;
    cmd.a = event_id;
    cmd.b = car_id;

    if (!CampaignExecuteCommand(&cmd) || !cmd.status) return 0;
    return cmd.out0;
}

int __cdecl CampaignFinishCareerFromPostRequest(void* post_request) {
    CampaignCommand cmd;
    int32_t position;
    int32_t race_time;
    int32_t stars;

    if (!post_request) return 0;

    position = DecodeAddressXorI32(post_request, 0x78);
    race_time = DecodeAddressXorI32(post_request, 0x7C);

    stars = 0;
    if (ReadU8(post_request, 0x68)) ++stars;
    if (ReadU8(post_request, 0x69)) ++stars;
    if (ReadU8(post_request, 0x6A)) ++stars;

    if (position <= 0 || race_time < 0) return 0;

    ZeroMemory(&cmd, sizeof(cmd));
    cmd.size = sizeof(cmd);
    cmd.op = CAMPAIGN_OP_FINISH_EVENT_RACE;
    cmd.a = 0; /* resolve active CampaignRaceSession.dat */
    cmd.b = position;
    cmd.c = stars;
    cmd.d = race_time;

    if (!CampaignExecuteCommand(&cmd) || !cmd.status) return 0;
    return 1;
}
