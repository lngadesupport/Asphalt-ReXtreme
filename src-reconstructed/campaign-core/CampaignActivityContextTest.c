#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignActivityContext.h"

static void Cleanup(void) {
    WCHAR path[1024];
    DWORD n;
    int i;
    uint32_t p,j;
    static const WCHAR* suffixes[] = {
        L"UserData\\CampaignEdition\\ActivityContext.dat",
        L"UserData\\CampaignEdition\\ActivityContext.tmp"
    };
    uint32_t s;
    for (s=0;s<2;++s) {
        for(j=0;j<1024;++j) path[j]=0;
        n=GetModuleFileNameW(0,path,1024);
        if(n==0||n>=1024)continue;
        i=(int)n-1;while(i>=0&&path[i]!=L'\\'&&path[i]!=L'/')--i;
        if(i<0)continue;p=(uint32_t)(i+1);j=0;
        while(suffixes[s][j]&&p+1<1024)path[p++]=suffixes[s][j++];
        path[p]=0;DeleteFileW(path);
    }
}

int main(void) {
    CampaignActivityContext in;
    CampaignActivityContext out;

    Cleanup();
    ZeroMemory(&in,sizeof(in));
    ZeroMemory(&out,sizeof(out));

    in.size=sizeof(in);
    in.version=CAMPAIGN_ACTIVITY_CONTEXT_VERSION;
    in.session_id=12345;
    in.activity_type=CAMPAIGN_ACTIVITY_SPECIAL_EVENT;
    in.activity_id=5001;
    in.slot_index=2;
    in.event_id=1003;
    in.period_key=202639u;

    if(!CampaignActivityContextSet(&in))return 1;

    out.size=sizeof(out);
    if(!CampaignActivityContextGet(&out))return 2;
    if(out.session_id!=12345||
       out.activity_type!=CAMPAIGN_ACTIVITY_SPECIAL_EVENT||
       out.activity_id!=5001||
       out.slot_index!=2||
       out.event_id!=1003||
       out.period_key!=202639u||
       out.result_valid)return 3;

    if(CampaignActivityContextSetResult(99999,1))return 4;
    if(!CampaignActivityContextSetResult(12345,2))return 5;

    ZeroMemory(&out,sizeof(out));out.size=sizeof(out);
    if(!CampaignActivityContextGet(&out))return 6;
    if(!out.result_valid||out.result_placement!=2)return 7;

    if(CampaignActivityContextClear(99999))return 8;
    if(!CampaignActivityContextClear(12345))return 9;
    ZeroMemory(&out,sizeof(out));out.size=sizeof(out);
    if(CampaignActivityContextGet(&out))return 10;

    in.session_id=22222;
    in.activity_type=CAMPAIGN_ACTIVITY_CHAMPIONSHIP;
    in.activity_id=7001;
    in.slot_index=1;
    in.event_id=1002;
    in.period_key=0;
    in.result_valid=0;
    in.result_placement=0;
    if(!CampaignActivityContextSet(&in))return 11;
    if(!CampaignActivityContextReset())return 12;

    Cleanup();
    return 0;
}
