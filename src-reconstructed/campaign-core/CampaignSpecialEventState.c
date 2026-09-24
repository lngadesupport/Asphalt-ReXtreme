#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignSpecialEventState.h"

#define RXSP_MAGIC 0x50535852u /* RXSP */

typedef struct CampaignSpecialEventPeriodEntry {
    int32_t special_event_id;
    uint32_t period_key;
    uint32_t stage_count;
    uint32_t reserved;
    uint32_t baseline_completion[CAMPAIGN_SPECIAL_EVENT_STAGE_MAX];
} CampaignSpecialEventPeriodEntry;

typedef struct CampaignSpecialEventPeriodFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignSpecialEventPeriodEntry entries[CAMPAIGN_SPECIAL_EVENT_MAX];
    uint32_t checksum;
} CampaignSpecialEventPeriodFile;

static CampaignSpecialEventPeriodFile g_period;
static CampaignSpecialEventPeriodFile g_load;
static volatile LONG g_loaded;
static volatile LONG g_lock;
static WCHAR g_path[1024];
static WCHAR g_tmp[1024];
static WCHAR g_exe[1024];
static WCHAR g_dir[1024];

static void SpZero(void* p,uint32_t n){
    volatile unsigned char* q=(volatile unsigned char*)p;uint32_t i;
    for(i=0;i<n;++i)q[i]=0;
}
static void SpCopy(void* d0,const void* s0,uint32_t n){
    volatile unsigned char* d=(volatile unsigned char*)d0;
    const volatile unsigned char* s=(const volatile unsigned char*)s0;uint32_t i;
    for(i=0;i<n;++i)d[i]=s[i];
}
static uint32_t SpHash(const void* p,uint32_t n){
    const unsigned char* s=(const unsigned char*)p;uint32_t h=2166136261u,i;
    for(i=0;i<n;++i){h^=s[i];h*=16777619u;}return h;
}
static void SpLock(void){while(InterlockedCompareExchange(&g_lock,1,0)!=0)Sleep(0);}
static void SpUnlock(void){InterlockedExchange(&g_lock,0);}
static int Append(WCHAR* d,uint32_t cap,const WCHAR* s){
    uint32_t n=0,i=0;if(!d||!s||cap==0)return 0;
    while(d[n]){++n;if(n>=cap)return 0;}
    while(s[i]){if(n+1>=cap)return 0;d[n++]=s[i++];}d[n]=0;return 1;
}
static int EnsureDir(const WCHAR* p){
    DWORD a=GetFileAttributesW(p);
    if(a!=INVALID_FILE_ATTRIBUTES)return(a&FILE_ATTRIBUTE_DIRECTORY)?1:0;
    if(CreateDirectoryW(p,0))return 1;
    return GetLastError()==ERROR_ALREADY_EXISTS?1:0;
}
static int BuildPaths(void){
    DWORD n;int i;
    if(g_path[0])return 1;
    SpZero(g_exe,sizeof(g_exe));SpZero(g_dir,sizeof(g_dir));
    n=GetModuleFileNameW(0,g_exe,1024);
    if(n==0||n>=1024)return 0;
    i=(int)n-1;while(i>=0&&g_exe[i]!=L'\\'&&g_exe[i]!=L'/')--i;
    if(i<0)return 0;g_exe[i+1]=0;
    if(!Append(g_dir,1024,g_exe)||!Append(g_dir,1024,L"UserData"))return 0;
    if(!EnsureDir(g_dir))return 0;
    if(!Append(g_dir,1024,L"\\CampaignEdition"))return 0;
    if(!EnsureDir(g_dir))return 0;
    if(!Append(g_path,1024,g_dir)||!Append(g_path,1024,L"\\SpecialEventPeriodState.dat"))return 0;
    if(!Append(g_tmp,1024,g_dir)||!Append(g_tmp,1024,L"\\SpecialEventPeriodState.tmp"))return 0;
    return 1;
}
static uint32_t Checksum(const CampaignSpecialEventPeriodFile* f){
    return SpHash(f,(uint32_t)sizeof(*f)-(uint32_t)sizeof(uint32_t));
}
static int EntryValid(const CampaignSpecialEventPeriodEntry* e){
    uint32_t i;
    if(!e||e->special_event_id<=0||e->period_key==0||
       e->stage_count==0||e->stage_count>CAMPAIGN_SPECIAL_EVENT_STAGE_MAX)return 0;
    for(i=e->stage_count;i<CAMPAIGN_SPECIAL_EVENT_STAGE_MAX;++i)
        if(e->baseline_completion[i]!=0)return 0;
    return 1;
}
static int FileValid(const CampaignSpecialEventPeriodFile* f){
    uint32_t i,j;
    if(!f||f->magic!=RXSP_MAGIC||
       f->version!=CAMPAIGN_SPECIAL_EVENT_PERIOD_STATE_VERSION||
       f->count>CAMPAIGN_SPECIAL_EVENT_MAX||
       f->checksum!=Checksum(f))return 0;
    for(i=0;i<f->count;++i){
        if(!EntryValid(&f->entries[i]))return 0;
        for(j=0;j<i;++j)
            if(f->entries[i].special_event_id==f->entries[j].special_event_id)return 0;
    }
    return 1;
}
static int WriteUnlocked(void){
    HANDLE h;DWORD written=0;
    if(!BuildPaths())return 0;
    g_period.magic=RXSP_MAGIC;
    g_period.version=CAMPAIGN_SPECIAL_EVENT_PERIOD_STATE_VERSION;
    g_period.checksum=Checksum(&g_period);
    DeleteFileW(g_tmp);
    h=CreateFileW(g_tmp,GENERIC_WRITE,FILE_SHARE_READ,0,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE)return 0;
    if(!WriteFile(h,&g_period,sizeof(g_period),&written,0)||written!=sizeof(g_period)){
        CloseHandle(h);DeleteFileW(g_tmp);return 0;
    }
    FlushFileBuffers(h);CloseHandle(h);
    if(!MoveFileExW(g_tmp,g_path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)){
        DeleteFileW(g_tmp);return 0;
    }
    return 1;
}
static int EnsureLoaded(void){
    HANDLE h;DWORD got=0;
    if(InterlockedCompareExchange(&g_loaded,1,1))return 1;
    SpLock();
    if(g_loaded){SpUnlock();return 1;}
    SpZero(&g_period,sizeof(g_period));SpZero(&g_load,sizeof(g_load));
    g_period.magic=RXSP_MAGIC;
    g_period.version=CAMPAIGN_SPECIAL_EVENT_PERIOD_STATE_VERSION;
    if(!BuildPaths()){SpUnlock();return 0;}
    h=CreateFileW(g_path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,0,
                  OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,0);
    if(h!=INVALID_HANDLE_VALUE){
        if(ReadFile(h,&g_load,sizeof(g_load),&got,0)&&got==sizeof(g_load)&&FileValid(&g_load))
            SpCopy(&g_period,&g_load,sizeof(g_period));
        CloseHandle(h);
    }
    InterlockedExchange(&g_loaded,1);
    if(GetFileAttributesW(g_path)==INVALID_FILE_ATTRIBUTES&&!WriteUnlocked()){
        SpUnlock();return 0;
    }
    SpUnlock();return 1;
}
static CampaignSpecialEventPeriodEntry* FindEntry(int32_t id){
    uint32_t i;
    for(i=0;i<g_period.count;++i)
        if(g_period.entries[i].special_event_id==id)return &g_period.entries[i];
    return 0;
}
static int IsRotating(const CampaignSpecialEventDefinition* d){
    if(!d)return 0;
    return d->schedule==CAMPAIGN_SPECIAL_EVENT_DAILY||
           d->schedule==CAMPAIGN_SPECIAL_EVENT_WEEKLY||
           d->schedule==CAMPAIGN_SPECIAL_EVENT_MONTHLY;
}

int CampaignSpecialEventPeriodStateEvaluate(
    const CampaignSpecialEventDefinition* def,
    uint32_t day_key,
    const uint32_t* completion_counts,
    uint32_t completion_count,
    uint32_t* completed_mask,
    uint32_t* completed_count
){
    uint32_t i,mask=0,count=0,period_key;
    CampaignSpecialEventPeriodEntry* e;
    int changed=0;

    if(completed_mask)*completed_mask=0;
    if(completed_count)*completed_count=0;
    if(!def||!completion_counts||completion_count!=def->stage_count||
       def->stage_count==0||def->stage_count>CAMPAIGN_SPECIAL_EVENT_STAGE_MAX)return 0;

    if(!IsRotating(def)){
        for(i=0;i<def->stage_count;++i){
            if(completion_counts[i]>0){
                mask|=(1u<<i);++count;
            }
        }
        if(completed_mask)*completed_mask=mask;
        if(completed_count)*completed_count=count;
        return 1;
    }

    period_key=CampaignSpecialEventPeriodKey(def,day_key);
    if(period_key==0||!EnsureLoaded())return 0;

    SpLock();
    e=FindEntry(def->special_event_id);
    if(!e){
        if(g_period.count>=CAMPAIGN_SPECIAL_EVENT_MAX){SpUnlock();return 0;}
        e=&g_period.entries[g_period.count++];
        SpZero(e,sizeof(*e));
        e->special_event_id=def->special_event_id;
        e->period_key=period_key;
        e->stage_count=def->stage_count;
        for(i=0;i<def->stage_count;++i)e->baseline_completion[i]=completion_counts[i];
        changed=1;
    }else if(e->period_key!=period_key||e->stage_count!=def->stage_count){
        int32_t id=e->special_event_id;
        SpZero(e,sizeof(*e));
        e->special_event_id=id;
        e->period_key=period_key;
        e->stage_count=def->stage_count;
        for(i=0;i<def->stage_count;++i)e->baseline_completion[i]=completion_counts[i];
        changed=1;
    }

    for(i=0;i<def->stage_count;++i){
        if(completion_counts[i]>e->baseline_completion[i]){
            mask|=(1u<<i);++count;
        }
    }

    if(changed&&!WriteUnlocked()){SpUnlock();return 0;}
    SpUnlock();
    if(completed_mask)*completed_mask=mask;
    if(completed_count)*completed_count=count;
    return 1;
}

int CampaignSpecialEventPeriodStateReload(void){
    SpLock();
    SpZero(&g_period,sizeof(g_period));SpZero(&g_load,sizeof(g_load));
    InterlockedExchange(&g_loaded,0);
    SpUnlock();
    return EnsureLoaded();
}
int CampaignSpecialEventPeriodStateReset(void){
    int ok;
    SpLock();
    SpZero(&g_period,sizeof(g_period));SpZero(&g_load,sizeof(g_load));
    g_period.magic=RXSP_MAGIC;
    g_period.version=CAMPAIGN_SPECIAL_EVENT_PERIOD_STATE_VERSION;
    InterlockedExchange(&g_loaded,1);
    if(!BuildPaths()){SpUnlock();return 0;}
    ok=DeleteFileW(g_path)||GetLastError()==ERROR_FILE_NOT_FOUND;
    DeleteFileW(g_tmp);
    if(ok)ok=WriteUnlocked();
    SpUnlock();return ok?1:0;
}
