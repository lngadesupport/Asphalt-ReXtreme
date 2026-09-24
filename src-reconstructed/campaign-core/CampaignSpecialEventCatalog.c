#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignSpecialEventCatalog.h"
#include "CampaignEventCatalog.h"

typedef struct CampaignSpecialEventCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignSpecialEventDefinition entries[CAMPAIGN_SPECIAL_EVENT_MAX];
    uint32_t checksum;
} CampaignSpecialEventCatalogFile;

static CampaignSpecialEventCatalogFile g_catalog;
static volatile LONG g_loaded;
static WCHAR g_path[1024];

static void ZeroBytes(void* p,uint32_t n){
    volatile unsigned char* q=(volatile unsigned char*)p;uint32_t i;
    for(i=0;i<n;++i)q[i]=0;
}
static uint32_t Hash(const void* p,uint32_t n){
    const unsigned char* s=(const unsigned char*)p;uint32_t h=2166136261u,i;
    for(i=0;i<n;++i){h^=s[i];h*=16777619u;}return h;
}
static uint32_t Checksum(const CampaignSpecialEventCatalogFile* f){
    return Hash(f,(uint32_t)sizeof(*f)-(uint32_t)sizeof(uint32_t));
}
static int BuildPath(void){
    HMODULE module;DWORD n;int i;uint32_t p,j=0;
    static const WCHAR name[]=L"CampaignSpecialEvents.dat";
    if(g_path[0])return 1;
    module=GetModuleHandleW(L"IGPLib_x86.dll");
    if(!module)module=GetModuleHandleW(0);
    if(!module)return 0;
    n=GetModuleFileNameW(module,g_path,1024);
    if(n==0||n>=1024)return 0;
    i=(int)n-1;while(i>=0&&g_path[i]!=L'\\'&&g_path[i]!=L'/')--i;
    if(i<0)return 0;p=(uint32_t)(i+1);
    while(name[j]){
        if(p+1>=1024)return 0;
        g_path[p++]=name[j++];
    }
    g_path[p]=0;return 1;
}
static int DayKeyShape(uint32_t k){
    uint32_t y,m,d;
    if(k==0)return 1;
    y=k/10000u;m=(k/100u)%100u;d=k%100u;
    return y>=2000u&&y<=9999u&&m>=1u&&m<=12u&&d>=1u&&d<=31u;
}
static int DefinitionValid(const CampaignSpecialEventDefinition* d){
    uint32_t i,j;
    if(!d||d->special_event_id<=0)return 0;
    if(d->schedule<CAMPAIGN_SPECIAL_EVENT_PERMANENT||
       d->schedule>CAMPAIGN_SPECIAL_EVENT_MANUAL)return 0;
    if(d->required_node_id<0)return 0;
    if(d->stage_count==0||d->stage_count>CAMPAIGN_SPECIAL_EVENT_STAGE_MAX)return 0;
    if(!DayKeyShape(d->start_day_key)||!DayKeyShape(d->end_day_key))return 0;
    if(d->start_day_key&&d->end_day_key&&d->start_day_key>d->end_day_key)return 0;
    if(d->schedule!=CAMPAIGN_SPECIAL_EVENT_MANUAL&&
       (d->flags&CAMPAIGN_SPECIAL_EVENT_MANUAL_ACTIVE))return 0;
    for(i=0;i<d->stage_count;++i){
        if(d->stage_event_ids[i]<=0)return 0;
        if(!CampaignEventCatalogFind(d->stage_event_ids[i]))return 0;
        for(j=0;j<i;++j)if(d->stage_event_ids[j]==d->stage_event_ids[i])return 0;
    }
    for(i=d->stage_count;i<CAMPAIGN_SPECIAL_EVENT_STAGE_MAX;++i)
        if(d->stage_event_ids[i]!=0)return 0;
    return 1;
}
static int CatalogValid(const CampaignSpecialEventCatalogFile* f){
    uint32_t i;
    if(!f||f->magic!=CAMPAIGN_SPECIAL_EVENT_MAGIC||
       f->version!=CAMPAIGN_SPECIAL_EVENT_VERSION||
       f->count>CAMPAIGN_SPECIAL_EVENT_MAX||
       f->checksum!=Checksum(f))return 0;
    for(i=0;i<f->count;++i){
        if(!DefinitionValid(&f->entries[i]))return 0;
        if(i>0&&f->entries[i-1].special_event_id>=f->entries[i].special_event_id)return 0;
    }
    return 1;
}
int CampaignSpecialEventCatalogEnsureLoaded(void){
    HANDLE h;DWORD got=0;
    if(InterlockedCompareExchange(&g_loaded,1,1))return g_catalog.count>0?1:0;
    ZeroBytes(&g_catalog,sizeof(g_catalog));
    if(!BuildPath()){InterlockedExchange(&g_loaded,1);return 0;}
    h=CreateFileW(g_path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,0,
                  OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE){InterlockedExchange(&g_loaded,1);return 0;}
    if(!ReadFile(h,&g_catalog,sizeof(g_catalog),&got,0)||got!=sizeof(g_catalog)){
        CloseHandle(h);ZeroBytes(&g_catalog,sizeof(g_catalog));
        InterlockedExchange(&g_loaded,1);return 0;
    }
    CloseHandle(h);
    if(!CatalogValid(&g_catalog)){
        ZeroBytes(&g_catalog,sizeof(g_catalog));InterlockedExchange(&g_loaded,1);return 0;
    }
    InterlockedExchange(&g_loaded,1);return 1;
}
uint32_t CampaignSpecialEventCatalogCount(void){
    CampaignSpecialEventCatalogEnsureLoaded();return g_catalog.count;
}
const CampaignSpecialEventDefinition* CampaignSpecialEventCatalogGet(uint32_t index){
    CampaignSpecialEventCatalogEnsureLoaded();
    if(index>=g_catalog.count)return 0;
    return &g_catalog.entries[index];
}
const CampaignSpecialEventDefinition* CampaignSpecialEventCatalogFind(int32_t id){
    int lo,hi;
    if(id<=0)return 0;
    CampaignSpecialEventCatalogEnsureLoaded();
    lo=0;hi=(int)g_catalog.count-1;
    while(lo<=hi){
        int mid=lo+((hi-lo)/2);int32_t cur=g_catalog.entries[mid].special_event_id;
        if(cur==id)return &g_catalog.entries[mid];
        if(cur<id)lo=mid+1;else hi=mid-1;
    }
    return 0;
}
int CampaignSpecialEventDateAvailable(const CampaignSpecialEventDefinition* d,uint32_t day){
    if(!d||!DayKeyShape(day)||day==0)return 0;
    if(d->start_day_key&&day<d->start_day_key)return 0;
    if(d->end_day_key&&day>d->end_day_key)return 0;
    if(d->schedule==CAMPAIGN_SPECIAL_EVENT_MANUAL&&
       !(d->flags&CAMPAIGN_SPECIAL_EVENT_MANUAL_ACTIVE))return 0;
    return 1;
}

static int SpecialEventLeap(uint32_t year){
    if((year%400u)==0u)return 1;
    if((year%100u)==0u)return 0;
    return(year%4u)==0u;
}
static uint32_t SpecialEventDayOfYear(uint32_t day_key){
    static const uint16_t before_month[12]={
        0,31,59,90,120,151,181,212,243,273,304,334
    };
    uint32_t year=day_key/10000u;
    uint32_t month=(day_key/100u)%100u;
    uint32_t day=day_key%100u;
    uint32_t result;
    if(year<2000u||month<1u||month>12u||day<1u||day>31u)return 0;
    result=(uint32_t)before_month[month-1u]+day;
    if(month>2u&&SpecialEventLeap(year))++result;
    return result;
}

uint32_t CampaignSpecialEventPeriodKey(
    const CampaignSpecialEventDefinition* d,
    uint32_t day_key
){
    uint32_t year,month,doy;
    if(!d||!DayKeyShape(day_key)||day_key==0)return 0;
    year=day_key/10000u;
    month=(day_key/100u)%100u;
    switch(d->schedule){
    case CAMPAIGN_SPECIAL_EVENT_DAILY:
        return day_key;
    case CAMPAIGN_SPECIAL_EVENT_WEEKLY:
        doy=SpecialEventDayOfYear(day_key);
        if(doy==0)return 0;
        return year*100u+((doy-1u)/7u+1u);
    case CAMPAIGN_SPECIAL_EVENT_MONTHLY:
        return year*100u+month;
    case CAMPAIGN_SPECIAL_EVENT_PERMANENT:
    case CAMPAIGN_SPECIAL_EVENT_UNLOCK:
    case CAMPAIGN_SPECIAL_EVENT_MANUAL:
        return 0;
    default:
        return 0;
    }
}
