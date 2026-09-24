#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignSeasonCatalog.h"
#include "CampaignEventCatalog.h"

typedef struct CampaignSeasonCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignSeasonDefinition entries[CAMPAIGN_SEASON_MAX];
    uint32_t checksum;
} CampaignSeasonCatalogFile;

static CampaignSeasonCatalogFile g_catalog;
static volatile LONG g_loaded;
static volatile LONG g_lock;
static WCHAR g_path[1024];

static void Zero(void* p,uint32_t n){
    volatile unsigned char* q=(volatile unsigned char*)p;uint32_t i;
    for(i=0;i<n;++i)q[i]=0;
}
static uint32_t Hash(const void* p,uint32_t n){
    const unsigned char* s=(const unsigned char*)p;uint32_t h=2166136261u,i;
    for(i=0;i<n;++i){h^=s[i];h*=16777619u;}return h;
}
static void Lock(void){while(InterlockedCompareExchange(&g_lock,1,0)!=0)Sleep(0);}
static void Unlock(void){InterlockedExchange(&g_lock,0);}
static int Append(WCHAR* d,uint32_t cap,const WCHAR* s){
    uint32_t n=0,i=0;if(!d||!s||cap==0)return 0;
    while(d[n]){++n;if(n>=cap)return 0;}
    while(s[i]){if(n+1>=cap)return 0;d[n++]=s[i++];}d[n]=0;return 1;
}
static int BuildPath(void){
    DWORD n;int i;uint32_t pos,j=0;
    static const WCHAR suffix[]=L"CampaignSeasons.dat";
    if(g_path[0])return 1;
    Zero(g_path,sizeof(g_path));
    n=GetModuleFileNameW(0,g_path,1024);
    if(n==0||n>=1024)return 0;
    i=(int)n-1;while(i>=0&&g_path[i]!=L'\\'&&g_path[i]!=L'/')--i;
    if(i<0)return 0;pos=(uint32_t)(i+1);
    while(suffix[j]){if(pos+1>=1024)return 0;g_path[pos++]=suffix[j++];}
    g_path[pos]=0;return 1;
}
static uint32_t Checksum(const CampaignSeasonCatalogFile* f){
    return Hash(f,(uint32_t)sizeof(*f)-(uint32_t)sizeof(uint32_t));
}
static int DefValid(const CampaignSeasonDefinition* d){
    uint32_t i,j;
    if(!d||d->season_id<=0||d->required_node_id<0||
       d->event_count==0||d->event_count>CAMPAIGN_SEASON_EVENT_MAX)return 0;
    for(i=0;i<d->event_count;++i){
        if(d->event_ids[i]<=0||!CampaignEventCatalogFind(d->event_ids[i]))return 0;
        for(j=0;j<i;++j)if(d->event_ids[j]==d->event_ids[i])return 0;
    }
    for(i=d->event_count;i<CAMPAIGN_SEASON_EVENT_MAX;++i)
        if(d->event_ids[i]!=0)return 0;
    return 1;
}
static int FileValid(const CampaignSeasonCatalogFile* f){
    uint32_t i;
    if(!f||f->magic!=CAMPAIGN_SEASON_MAGIC||
       f->version!=CAMPAIGN_SEASON_VERSION||
       f->count>CAMPAIGN_SEASON_MAX||
       f->checksum!=Checksum(f))return 0;
    for(i=0;i<f->count;++i){
        if(!DefValid(&f->entries[i]))return 0;
        if(i>0&&f->entries[i-1].season_id>=f->entries[i].season_id)return 0;
    }
    return 1;
}
int CampaignSeasonCatalogEnsureLoaded(void){
    HANDLE h;DWORD got=0;
    if(InterlockedCompareExchange(&g_loaded,1,1))return g_catalog.count>0?1:0;
    Lock();
    if(g_loaded){int ok=g_catalog.count>0?1:0;Unlock();return ok;}
    Zero(&g_catalog,sizeof(g_catalog));
    if(!BuildPath()){InterlockedExchange(&g_loaded,1);Unlock();return 0;}
    h=CreateFileW(g_path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,0,
                  OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE){InterlockedExchange(&g_loaded,1);Unlock();return 0;}
    if(!ReadFile(h,&g_catalog,sizeof(g_catalog),&got,0)||got!=sizeof(g_catalog)){
        CloseHandle(h);Zero(&g_catalog,sizeof(g_catalog));
        InterlockedExchange(&g_loaded,1);Unlock();return 0;
    }
    CloseHandle(h);
    if(!FileValid(&g_catalog)){
        Zero(&g_catalog,sizeof(g_catalog));InterlockedExchange(&g_loaded,1);Unlock();return 0;
    }
    InterlockedExchange(&g_loaded,1);Unlock();return 1;
}
uint32_t CampaignSeasonCatalogCount(void){
    CampaignSeasonCatalogEnsureLoaded();return g_catalog.count;
}
const CampaignSeasonDefinition* CampaignSeasonCatalogGet(uint32_t index){
    CampaignSeasonCatalogEnsureLoaded();
    if(index>=g_catalog.count)return 0;return &g_catalog.entries[index];
}
const CampaignSeasonDefinition* CampaignSeasonCatalogFind(int32_t id){
    int lo=0,hi;
    if(id<=0)return 0;
    CampaignSeasonCatalogEnsureLoaded();hi=(int)g_catalog.count-1;
    while(lo<=hi){
        int mid=lo+((hi-lo)/2);int32_t cur=g_catalog.entries[mid].season_id;
        if(cur==id)return &g_catalog.entries[mid];
        if(cur<id)lo=mid+1;else hi=mid-1;
    }
    return 0;
}
