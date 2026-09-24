#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignChampionshipCatalog.h"
#include "CampaignEventCatalog.h"

#define RXHS_MAGIC 0x53485852u /* RXHS */

typedef struct CampaignChampionshipCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignChampionshipDefinition entries[CAMPAIGN_CHAMPIONSHIP_MAX];
    uint32_t checksum;
} CampaignChampionshipCatalogFile;

typedef struct CampaignChampionshipStateEntry {
    int32_t championship_id;
    int32_t best_placements[CAMPAIGN_CHAMPIONSHIP_ROUND_MAX];
    int32_t total_points;
    uint32_t completed;
} CampaignChampionshipStateEntry;

typedef struct CampaignChampionshipStateFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignChampionshipStateEntry entries[CAMPAIGN_CHAMPIONSHIP_MAX];
    uint32_t checksum;
} CampaignChampionshipStateFile;

static CampaignChampionshipCatalogFile g_catalog;
static CampaignChampionshipStateFile g_state;
static CampaignChampionshipStateFile g_load;
static volatile LONG g_catalog_loaded;
static volatile LONG g_state_loaded;
static volatile LONG g_lock;
static WCHAR g_catalog_path[1024];
static WCHAR g_state_path[1024];
static WCHAR g_state_tmp[1024];
static WCHAR g_exe[1024];
static WCHAR g_dir[1024];

static void ChZero(void* p,uint32_t n){
    volatile unsigned char* q=(volatile unsigned char*)p;uint32_t i;
    for(i=0;i<n;++i)q[i]=0;
}
static void ChCopy(void* d0,const void* s0,uint32_t n){
    volatile unsigned char* d=(volatile unsigned char*)d0;
    const volatile unsigned char* s=(const volatile unsigned char*)s0;uint32_t i;
    for(i=0;i<n;++i)d[i]=s[i];
}
static uint32_t ChHash(const void* p,uint32_t n){
    const unsigned char* s=(const unsigned char*)p;uint32_t h=2166136261u,i;
    for(i=0;i<n;++i){h^=s[i];h*=16777619u;}return h;
}
static void ChLock(void){while(InterlockedCompareExchange(&g_lock,1,0)!=0)Sleep(0);}
static void ChUnlock(void){InterlockedExchange(&g_lock,0);}
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
    if(g_catalog_path[0]&&g_state_path[0])return 1;
    ChZero(g_exe,sizeof(g_exe));ChZero(g_dir,sizeof(g_dir));
    n=GetModuleFileNameW(0,g_exe,1024);
    if(n==0||n>=1024)return 0;
    i=(int)n-1;while(i>=0&&g_exe[i]!=L'\\'&&g_exe[i]!=L'/')--i;
    if(i<0)return 0;g_exe[i+1]=0;

    if(!Append(g_catalog_path,1024,g_exe)||
       !Append(g_catalog_path,1024,L"CampaignChampionships.dat"))return 0;

    if(!Append(g_dir,1024,g_exe)||!Append(g_dir,1024,L"UserData"))return 0;
    if(!EnsureDir(g_dir))return 0;
    if(!Append(g_dir,1024,L"\\CampaignEdition"))return 0;
    if(!EnsureDir(g_dir))return 0;

    if(!Append(g_state_path,1024,g_dir)||
       !Append(g_state_path,1024,L"\\ChampionshipState.dat"))return 0;
    if(!Append(g_state_tmp,1024,g_dir)||
       !Append(g_state_tmp,1024,L"\\ChampionshipState.tmp"))return 0;
    return 1;
}
static uint32_t CatalogChecksum(const CampaignChampionshipCatalogFile* f){
    return ChHash(f,(uint32_t)sizeof(*f)-(uint32_t)sizeof(uint32_t));
}
static uint32_t StateChecksum(const CampaignChampionshipStateFile* f){
    return ChHash(f,(uint32_t)sizeof(*f)-(uint32_t)sizeof(uint32_t));
}
static int DefValid(const CampaignChampionshipDefinition* d){
    uint32_t i,j;
    int previous=0;
    if(!d||d->championship_id<=0||d->required_node_id<0||
       d->round_count==0||d->round_count>CAMPAIGN_CHAMPIONSHIP_ROUND_MAX)return 0;
    for(i=0;i<d->round_count;++i){
        if(d->round_event_ids[i]<=0||!CampaignEventCatalogFind(d->round_event_ids[i]))return 0;
        for(j=0;j<i;++j)if(d->round_event_ids[j]==d->round_event_ids[i])return 0;
    }
    for(i=d->round_count;i<CAMPAIGN_CHAMPIONSHIP_ROUND_MAX;++i)
        if(d->round_event_ids[i]!=0)return 0;
    for(i=0;i<CAMPAIGN_CHAMPIONSHIP_POSITION_MAX;++i){
        if(d->points_by_position[i]<0)return 0;
        if(i>0&&d->points_by_position[i]>previous)return 0;
        previous=d->points_by_position[i];
    }
    if(d->points_by_position[0]<=0)return 0;
    return 1;
}
static int CatalogValid(const CampaignChampionshipCatalogFile* f){
    uint32_t i;
    if(!f||f->magic!=CAMPAIGN_CHAMPIONSHIP_MAGIC||
       f->version!=CAMPAIGN_CHAMPIONSHIP_VERSION||
       f->count>CAMPAIGN_CHAMPIONSHIP_MAX||
       f->checksum!=CatalogChecksum(f))return 0;
    for(i=0;i<f->count;++i){
        if(!DefValid(&f->entries[i]))return 0;
        if(i>0&&f->entries[i-1].championship_id>=f->entries[i].championship_id)return 0;
    }
    return 1;
}
int CampaignChampionshipCatalogEnsureLoaded(void){
    HANDLE h;DWORD got=0;
    if(InterlockedCompareExchange(&g_catalog_loaded,1,1))return g_catalog.count>0?1:0;
    ChLock();
    if(g_catalog_loaded){int ok=g_catalog.count>0?1:0;ChUnlock();return ok;}
    ChZero(&g_catalog,sizeof(g_catalog));
    if(!BuildPaths()){InterlockedExchange(&g_catalog_loaded,1);ChUnlock();return 0;}
    h=CreateFileW(g_catalog_path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,0,
                  OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE){InterlockedExchange(&g_catalog_loaded,1);ChUnlock();return 0;}
    if(!ReadFile(h,&g_catalog,sizeof(g_catalog),&got,0)||got!=sizeof(g_catalog)){
        CloseHandle(h);ChZero(&g_catalog,sizeof(g_catalog));
        InterlockedExchange(&g_catalog_loaded,1);ChUnlock();return 0;
    }
    CloseHandle(h);
    if(!CatalogValid(&g_catalog)){
        ChZero(&g_catalog,sizeof(g_catalog));InterlockedExchange(&g_catalog_loaded,1);
        ChUnlock();return 0;
    }
    InterlockedExchange(&g_catalog_loaded,1);ChUnlock();return 1;
}
uint32_t CampaignChampionshipCatalogCount(void){
    CampaignChampionshipCatalogEnsureLoaded();return g_catalog.count;
}
const CampaignChampionshipDefinition* CampaignChampionshipCatalogGet(uint32_t index){
    CampaignChampionshipCatalogEnsureLoaded();
    if(index>=g_catalog.count)return 0;return &g_catalog.entries[index];
}
const CampaignChampionshipDefinition* CampaignChampionshipCatalogFind(int32_t id){
    int lo=0,hi;
    if(id<=0)return 0;
    CampaignChampionshipCatalogEnsureLoaded();hi=(int)g_catalog.count-1;
    while(lo<=hi){
        int mid=lo+((hi-lo)/2);int32_t cur=g_catalog.entries[mid].championship_id;
        if(cur==id)return &g_catalog.entries[mid];
        if(cur<id)lo=mid+1;else hi=mid-1;
    }
    return 0;
}
static CampaignChampionshipStateEntry* StateFind(int32_t id){
    uint32_t i;
    for(i=0;i<g_state.count;++i)
        if(g_state.entries[i].championship_id==id)return &g_state.entries[i];
    return 0;
}
static int StateValid(const CampaignChampionshipStateFile* f){
    uint32_t i,j,k;
    if(!f||f->magic!=RXHS_MAGIC||f->version!=CAMPAIGN_CHAMPIONSHIP_VERSION||
       f->count>CAMPAIGN_CHAMPIONSHIP_MAX||f->checksum!=StateChecksum(f))return 0;
    for(i=0;i<f->count;++i){
        if(f->entries[i].championship_id<=0||f->entries[i].total_points<0||
           f->entries[i].completed>1)return 0;
        for(k=0;k<CAMPAIGN_CHAMPIONSHIP_ROUND_MAX;++k)
            if(f->entries[i].best_placements[k]<0||
               f->entries[i].best_placements[k]>CAMPAIGN_CHAMPIONSHIP_POSITION_MAX)return 0;
        for(j=0;j<i;++j)
            if(f->entries[i].championship_id==f->entries[j].championship_id)return 0;
    }
    return 1;
}
static int WriteStateUnlocked(void){
    HANDLE h;DWORD written=0;
    if(!BuildPaths())return 0;
    g_state.magic=RXHS_MAGIC;g_state.version=CAMPAIGN_CHAMPIONSHIP_VERSION;
    g_state.checksum=StateChecksum(&g_state);
    DeleteFileW(g_state_tmp);
    h=CreateFileW(g_state_tmp,GENERIC_WRITE,FILE_SHARE_READ,0,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE)return 0;
    if(!WriteFile(h,&g_state,sizeof(g_state),&written,0)||written!=sizeof(g_state)){
        CloseHandle(h);DeleteFileW(g_state_tmp);return 0;
    }
    FlushFileBuffers(h);CloseHandle(h);
    if(!MoveFileExW(g_state_tmp,g_state_path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)){
        DeleteFileW(g_state_tmp);return 0;
    }
    return 1;
}
static int SyncUnlocked(int* changed){
    uint32_t i;
    if(changed)*changed=0;
    if(!CampaignChampionshipCatalogEnsureLoaded())return 0;
    for(i=0;i<g_catalog.count;++i){
        int32_t id=g_catalog.entries[i].championship_id;
        if(!StateFind(id)){
            CampaignChampionshipStateEntry* e;
            if(g_state.count>=CAMPAIGN_CHAMPIONSHIP_MAX)return 0;
            e=&g_state.entries[g_state.count++];ChZero(e,sizeof(*e));e->championship_id=id;
            if(changed)*changed=1;
        }
    }
    return 1;
}
int CampaignChampionshipsEnsureLoaded(void){
    HANDLE h;DWORD got=0;int changed=0;
    if(InterlockedCompareExchange(&g_state_loaded,1,1))return 1;
    if(!CampaignChampionshipCatalogEnsureLoaded())return 0;
    ChLock();
    if(g_state_loaded){ChUnlock();return 1;}
    ChZero(&g_state,sizeof(g_state));ChZero(&g_load,sizeof(g_load));
    g_state.magic=RXHS_MAGIC;g_state.version=CAMPAIGN_CHAMPIONSHIP_VERSION;
    if(!BuildPaths()){ChUnlock();return 0;}
    h=CreateFileW(g_state_path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,0,
                  OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,0);
    if(h!=INVALID_HANDLE_VALUE){
        if(ReadFile(h,&g_load,sizeof(g_load),&got,0)&&got==sizeof(g_load)&&StateValid(&g_load))
            ChCopy(&g_state,&g_load,sizeof(g_state));
        CloseHandle(h);
    }
    if(!SyncUnlocked(&changed)){ChUnlock();return 0;}
    InterlockedExchange(&g_state_loaded,1);
    if((changed||GetFileAttributesW(g_state_path)==INVALID_FILE_ATTRIBUTES)&&!WriteStateUnlocked()){
        ChUnlock();return 0;
    }
    ChUnlock();return 1;
}
static int RoundIndex(const CampaignChampionshipDefinition* d,int32_t event_id){
    uint32_t i;if(!d)return -1;
    for(i=0;i<d->round_count;++i)if(d->round_event_ids[i]==event_id)return(int)i;
    return -1;
}
static int CompletedRounds(const CampaignChampionshipDefinition* d,const CampaignChampionshipStateEntry* e){
    uint32_t i;int count=0;
    if(!d||!e)return 0;
    for(i=0;i<d->round_count;++i)if(e->best_placements[i]>0)++count;
    return count;
}
int CampaignChampionshipsRecordRound(
    int32_t championship_id,int32_t event_id,const CampaignRaceMetrics* metrics
){
    const CampaignChampionshipDefinition* d;
    CampaignChampionshipStateEntry* e;
    int index,old_placement,new_points,old_points=0;
    if(!metrics||metrics->size<sizeof(*metrics)||metrics->version!=CAMPAIGN_RACE_METRICS_VERSION||
       metrics->placement<=0||metrics->placement>CAMPAIGN_CHAMPIONSHIP_POSITION_MAX)return 0;
    if(!CampaignChampionshipsEnsureLoaded())return 0;
    d=CampaignChampionshipCatalogFind(championship_id);if(!d)return 0;
    index=RoundIndex(d,event_id);if(index<0)return 0;
    ChLock();e=StateFind(championship_id);if(!e){ChUnlock();return 0;}
    old_placement=e->best_placements[index];
    if(old_placement>0)old_points=d->points_by_position[old_placement-1];
    new_points=d->points_by_position[metrics->placement-1];

    if(old_placement==0||new_points>old_points){
        int delta=new_points-old_points;
        if(delta<0||e->total_points>0x7FFFFFFF-delta){ChUnlock();return 0;}
        e->best_placements[index]=metrics->placement;
        e->total_points+=delta;
    }
    e->completed=CompletedRounds(d,e)==(int)d->round_count?1u:0u;
    if(!WriteStateUnlocked()){ChUnlock();return 0;}
    ChUnlock();return 1;
}
int CampaignChampionshipsGetStatus(int32_t id,CampaignChampionshipStatus* out){
    const CampaignChampionshipDefinition* d;CampaignChampionshipStateEntry* e;
    if(!out||out->size<sizeof(*out)||!CampaignChampionshipsEnsureLoaded())return 0;
    d=CampaignChampionshipCatalogFind(id);if(!d)return 0;
    ChLock();e=StateFind(id);if(!e){ChUnlock();return 0;}
    out->size=sizeof(*out);out->championship_id=id;out->round_count=d->round_count;
    out->completed_rounds=(uint32_t)CompletedRounds(d,e);out->completed=e->completed;
    out->total_points=e->total_points;ChUnlock();return 1;
}
int CampaignChampionshipsGetRoundStatus(
    int32_t id,uint32_t round_index,CampaignChampionshipRoundStatus* out
){
    const CampaignChampionshipDefinition* d;CampaignChampionshipStateEntry* e;int placement;
    if(!out||out->size<sizeof(*out)||!CampaignChampionshipsEnsureLoaded())return 0;
    d=CampaignChampionshipCatalogFind(id);if(!d||round_index>=d->round_count)return 0;
    ChLock();e=StateFind(id);if(!e){ChUnlock();return 0;}
    placement=e->best_placements[round_index];
    out->size=sizeof(*out);out->championship_id=id;out->round_index=round_index;
    out->event_id=d->round_event_ids[round_index];out->best_placement=placement;
    out->points=placement>0?d->points_by_position[placement-1]:0;
    out->completed=placement>0?1u:0u;ChUnlock();return 1;
}
int CampaignChampionshipsReload(void){
    ChLock();
    ChZero(&g_state,sizeof(g_state));ChZero(&g_load,sizeof(g_load));
    InterlockedExchange(&g_state_loaded,0);
    ChUnlock();
    return CampaignChampionshipsEnsureLoaded();
}
int CampaignChampionshipsResetState(void){
    int ok;
    ChLock();ChZero(&g_state,sizeof(g_state));ChZero(&g_load,sizeof(g_load));
    InterlockedExchange(&g_state_loaded,0);
    if(!BuildPaths()){ChUnlock();return 0;}
    ok=DeleteFileW(g_state_path)||GetLastError()==ERROR_FILE_NOT_FOUND;
    DeleteFileW(g_state_tmp);ChUnlock();return ok?1:0;
}
