#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

int __cdecl CampaignBeginCareerFromPreRequest(void* pre_request);
int __cdecl CampaignFinishCareerFromPostRequest(void* post_request);

#ifdef __cplusplus
}
#endif
