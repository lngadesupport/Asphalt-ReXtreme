#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignAchievementCatalog.h"

#define RXAS_MAGIC 0x53415852u /* RXAS */

typedef struct CampaignAchievementCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignAchievementDefinition entries[CAMPAIGN_ACHIEVEMENT_MAX];
    uint32_t checksum;
} CampaignAchievementCatalogFile;

typedef struct CampaignAchievementStateEntry {
    int32_t achievement_id;
    uint32_t completed;
    uint32_t unlocked_day_key;
    uint32_t reserved;
} CampaignAchievementStateEntry;

typedef struct CampaignAchievementStateFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignAchievementStateEntry entries[CAMPAIGN_ACHIEVEMENT_MAX];
    uint32_t checksum;
} CampaignAchievementStateFile;

static CampaignAchievementCatalogFile g_catalog;
static CampaignAchievementStateFile g_state;
static CampaignAchievementStateFile g_load;
static volatile LONG g_catalog_loaded;
static volatile LONG g_state_loaded;
static volatile LONG g_lock;
static WCHAR g_catalog_path[1024];
static WCHAR g_state_dir[1024];
static WCHAR g_state_path[1024];
static WCHAR g_state_tmp[1024];

static void AchZero(void* p,uint32_t n){
    volatile unsigned char* q=(volatile unsigned char*)p;uint32_t i;
    for(i=0;i<n;++i)q[i]=0;
}
static void AchCopy(void* d0,const void* s0,uint32_t n){
    volatile unsigned char* d=(volatile unsigned char*)d0;
    const volatile unsigned char* s=(const volatile unsigned char*)s0;uint32_t i;
    for(i=0;i<n;++i)d[i]=s[i];
}
static uint32_t AchHash(const void* p,uint32_t n){
    const unsigned char* s=(const unsigned char*)p;uint32_t h=2166136261u,i;
    for(i=0;i<n;++i){h^=s[i];h*=16777619u;}return h;
}
static void AchLock(void){while(InterlockedCompareExchange(&g_lock,1,0)!=0)Sleep(0);}
static void AchUnlock(void){InterlockedExchange(&g_lock,0);}
static int WideAppend(WCHAR* d,uint32_t cap,const WCHAR* s){
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
    WCHAR exe[1024];DWORD n;int i;
    if(g_catalog_path[0]&&g_state_path[0])return 1;
    AchZero(exe,sizeof(exe));n=GetModuleFileNameW(0,exe,1024);
    if(n==0||n>=1024)return 0;i=(int)n-1;
    while(i>=0&&exe[i]!=L'\\'&&exe[i]!=L'/')--i;
    if(i<0)return 0;exe[i+1]=0;

    if(!WideAppend(g_catalog_path,1024,exe)||!WideAppend(g_catalog_path,1024,L"CampaignAchievements.dat"))return 0;
    if(!WideAppend(g_state_dir,1024,exe)||!WideAppend(g_state_dir,1024,L"UserData"))return 0;
    if(!EnsureDir(g_state_dir))return 0;
    if(!WideAppend(g_state_dir,1024,L"\\CampaignEdition"))return 0;
    if(!EnsureDir(g_state_dir))return 0;
    if(!WideAppend(g_state_path,1024,g_state_dir)||!WideAppend(g_state_path,1024,L"\\AchievementState.dat"))return 0;
    if(!WideAppend(g_state_tmp,1024,g_state_dir)||!WideAppend(g_state_tmp,1024,L"\\AchievementState.tmp"))return 0;
    return 1;
}
static uint32_t CatalogChecksum(const CampaignAchievementCatalogFile* f){
    return AchHash(f,sizeof(*f)-sizeof(uint32_t));
}
static uint32_t StateChecksum(const CampaignAchievementStateFile* f){
    return AchHash(f,sizeof(*f)-sizeof(uint32_t));
}
static int DefValid(const CampaignAchievementDefinition* d){
    if(!d||d->achievement_id<=0)return 0;
    if(d->metric<CAMPAIGN_ACHIEVEMENT_RACES||d->metric>CAMPAIGN_ACHIEVEMENT_NITRO_NORMAL)return 0;
    if(d->compare!=CAMPAIGN_COMPARE_LE&&d->compare!=CAMPAIGN_COMPARE_GE&&d->compare!=CAMPAIGN_COMPARE_EQ)return 0;
    if(d->threshold==0)return 0;
    return 1;
}
static int CatalogValid(const CampaignAchievementCatalogFile* f){
    uint32_t i;
    if(!f||f->magic!=CAMPAIGN_ACHIEVEMENT_MAGIC||f->version!=CAMPAIGN_ACHIEVEMENT_VERSION||
       f->count>CAMPAIGN_ACHIEVEMENT_MAX||f->checksum!=CatalogChecksum(f))return 0;
    for(i=0;i<f->count;++i){
        if(!DefValid(&f->entries[i]))return 0;
        if(i>0&&f->entries[i-1].achievement_id>=f->entries[i].achievement_id)return 0;
    }
    return 1;
}

int CampaignAchievementCatalogEnsureLoaded(void){
    HANDLE h;DWORD got=0;
    if(InterlockedCompareExchange(&g_catalog_loaded,1,1))return g_catalog.count>0?1:0;
    AchLock();
    if(g_catalog_loaded){AchUnlock();return g_catalog.count>0?1:0;}
    AchZero(&g_catalog,sizeof(g_catalog));
    if(!BuildPaths()){InterlockedExchange(&g_catalog_loaded,1);AchUnlock();return 0;}
    h=CreateFileW(g_catalog_path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,0,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE){InterlockedExchange(&g_catalog_loaded,1);AchUnlock();return 0;}
    if(!ReadFile(h,&g_catalog,sizeof(g_catalog),&got,0)||got!=sizeof(g_catalog)){
        CloseHandle(h);AchZero(&g_catalog,sizeof(g_catalog));InterlockedExchange(&g_catalog_loaded,1);AchUnlock();return 0;
    }
    CloseHandle(h);
    if(!CatalogValid(&g_catalog)){AchZero(&g_catalog,sizeof(g_catalog));InterlockedExchange(&g_catalog_loaded,1);AchUnlock();return 0;}
    InterlockedExchange(&g_catalog_loaded,1);AchUnlock();return 1;
}
uint32_t CampaignAchievementCatalogCount(void){CampaignAchievementCatalogEnsureLoaded();return g_catalog.count;}
const CampaignAchievementDefinition* CampaignAchievementCatalogGet(uint32_t index){
    CampaignAchievementCatalogEnsureLoaded();if(index>=g_catalog.count)return 0;return &g_catalog.entries[index];
}
const CampaignAchievementDefinition* CampaignAchievementCatalogFind(int32_t id){
    int lo=0,hi;CampaignAchievementCatalogEnsureLoaded();hi=(int)g_catalog.count-1;
    while(lo<=hi){int mid=lo+((hi-lo)/2);int32_t x=g_catalog.entries[mid].achievement_id;
        if(x==id)return &g_catalog.entries[mid];if(x<id)lo=mid+1;else hi=mid-1;}
    return 0;
}
static CampaignAchievementStateEntry* StateFind(int32_t id){
    uint32_t i;for(i=0;i<g_state.count;++i)if(g_state.entries[i].achievement_id==id)return &g_state.entries[i];return 0;
}
static int StateValid(const CampaignAchievementStateFile* f){
    uint32_t i,j;
    if(!f||f->magic!=RXAS_MAGIC||f->version!=CAMPAIGN_ACHIEVEMENT_VERSION||
       f->count>CAMPAIGN_ACHIEVEMENT_MAX||f->checksum!=StateChecksum(f))return 0;
    for(i=0;i<f->count;++i){
        if(f->entries[i].achievement_id<=0||f->entries[i].completed>1)return 0;
        for(j=0;j<i;++j)if(f->entries[i].achievement_id==f->entries[j].achievement_id)return 0;
    }return 1;
}
static int WriteUnlocked(void){
    HANDLE h;DWORD written=0;
    if(!BuildPaths())return 0;g_state.magic=RXAS_MAGIC;g_state.version=CAMPAIGN_ACHIEVEMENT_VERSION;
    g_state.checksum=StateChecksum(&g_state);DeleteFileW(g_state_tmp);
    h=CreateFileW(g_state_tmp,GENERIC_WRITE,FILE_SHARE_READ,0,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE)return 0;
    if(!WriteFile(h,&g_state,sizeof(g_state),&written,0)||written!=sizeof(g_state)){
        CloseHandle(h);DeleteFileW(g_state_tmp);return 0;}
    FlushFileBuffers(h);CloseHandle(h);
    if(!MoveFileExW(g_state_tmp,g_state_path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)){
        DeleteFileW(g_state_tmp);return 0;}return 1;
}
static int SyncUnlocked(int* changed){
    uint32_t i;if(changed)*changed=0;
    if(!CampaignAchievementCatalogEnsureLoaded())return 0;
    for(i=0;i<g_catalog.count;++i){
        int32_t id=g_catalog.entries[i].achievement_id;
        if(!StateFind(id)){
            CampaignAchievementStateEntry* e;
            if(g_state.count>=CAMPAIGN_ACHIEVEMENT_MAX)return 0;
            e=&g_state.entries[g_state.count++];AchZero(e,sizeof(*e));e->achievement_id=id;
            if(changed)*changed=1;
        }
    }return 1;
}
int CampaignAchievementsEnsureLoaded(void){
    HANDLE h;DWORD got=0;int changed=0;
    if(InterlockedCompareExchange(&g_state_loaded,1,1))return 1;
    if(!CampaignAchievementCatalogEnsureLoaded())return 0;
    AchLock();
    if(g_state_loaded){AchUnlock();return 1;}
    AchZero(&g_state,sizeof(g_state));AchZero(&g_load,sizeof(g_load));
    g_state.magic=RXAS_MAGIC;g_state.version=CAMPAIGN_ACHIEVEMENT_VERSION;
    if(!BuildPaths()){AchUnlock();return 0;}
    h=CreateFileW(g_state_path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,0,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,0);
    if(h!=INVALID_HANDLE_VALUE){
        if(ReadFile(h,&g_load,sizeof(g_load),&got,0)&&got==sizeof(g_load)&&StateValid(&g_load))
            AchCopy(&g_state,&g_load,sizeof(g_state));
        CloseHandle(h);
    }
    if(!SyncUnlocked(&changed)){AchUnlock();return 0;}
    InterlockedExchange(&g_state_loaded,1);
    if((changed||GetFileAttributesW(g_state_path)==INVALID_FILE_ATTRIBUTES)&&!WriteUnlocked()){
        AchUnlock();return 0;}
    AchUnlock();return 1;
}
static uint32_t CurrentDayKey(void){
    SYSTEMTIME st;GetLocalTime(&st);
    return(uint32_t)st.wYear*10000u+(uint32_t)st.wMonth*100u+(uint32_t)st.wDay;
}
static int MetricValue(const CampaignStatisticsSnapshot* s,uint32_t metric,uint32_t* out){
    if(!s||!out)return 0;
    switch(metric){
    case CAMPAIGN_ACHIEVEMENT_RACES:*out=s->races_with_metrics;return 1;
    case CAMPAIGN_ACHIEVEMENT_WINS:*out=s->wins;return 1;
    case CAMPAIGN_ACHIEVEMENT_PODIUMS:*out=s->podiums;return 1;
    case CAMPAIGN_ACHIEVEMENT_BEST_PLACEMENT:*out=s->best_placement;return 1;
    case CAMPAIGN_ACHIEVEMENT_BEST_FINISH_TIME_MS:*out=s->best_finish_time_ms;return 1;
    case CAMPAIGN_ACHIEVEMENT_DRIFT_METERS:*out=s->total_drift_meters;return 1;
    case CAMPAIGN_ACHIEVEMENT_AIR_TIME_MS:*out=s->total_air_time_ms;return 1;
    case CAMPAIGN_ACHIEVEMENT_NITRO_TIME_MS:*out=s->total_nitro_time_ms;return 1;
    case CAMPAIGN_ACHIEVEMENT_WRECKED_CARS:*out=s->total_wrecked_cars;return 1;
    case CAMPAIGN_ACHIEVEMENT_WRECKED_ENVIRONMENT:*out=s->total_wrecked_environment;return 1;
    case CAMPAIGN_ACHIEVEMENT_WRECKS_MADE:*out=s->total_wrecks_made;return 1;
    case CAMPAIGN_ACHIEVEMENT_FLAT_SPINS:*out=s->total_flat_spins;return 1;
    case CAMPAIGN_ACHIEVEMENT_BARREL_ROLLS:*out=s->total_barrel_rolls;return 1;
    case CAMPAIGN_ACHIEVEMENT_OBSTACLES_BROKEN:*out=s->total_obstacles_broken;return 1;
    case CAMPAIGN_ACHIEVEMENT_NITRO_ALL_IN:*out=s->total_nitro_all_in;return 1;
    case CAMPAIGN_ACHIEVEMENT_NITRO_CHAIN:*out=s->total_nitro_chain;return 1;
    case CAMPAIGN_ACHIEVEMENT_NITRO_NORMAL:*out=s->total_nitro_normal;return 1;
    default:return 0;}
}
static int Compare(uint32_t value,uint32_t op,uint32_t threshold){
    if(op==CAMPAIGN_COMPARE_LE)return value<=threshold;
    if(op==CAMPAIGN_COMPARE_GE)return value>=threshold;
    if(op==CAMPAIGN_COMPARE_EQ)return value==threshold;
    return 0;
}
int CampaignAchievementsRefresh(void){
    CampaignStatisticsSnapshot stats;uint32_t i;int changed=0;
    AchZero(&stats,sizeof(stats));stats.size=sizeof(stats);
    if(!CampaignAchievementsEnsureLoaded()||!CampaignStatisticsGet(&stats))return 0;
    AchLock();
    for(i=0;i<g_catalog.count;++i){
        const CampaignAchievementDefinition* d=&g_catalog.entries[i];
        CampaignAchievementStateEntry* e=StateFind(d->achievement_id);
        uint32_t value=0;
        if(!e||e->completed||!MetricValue(&stats,d->metric,&value))continue;
        if((d->metric==CAMPAIGN_ACHIEVEMENT_BEST_PLACEMENT||
            d->metric==CAMPAIGN_ACHIEVEMENT_BEST_FINISH_TIME_MS)&&value==0)continue;
        if(Compare(value,d->compare,d->threshold)){
            e->completed=1;e->unlocked_day_key=CurrentDayKey();changed=1;
        }
    }
    if(changed&&!WriteUnlocked()){AchUnlock();return 0;}
    AchUnlock();return 1;
}
static int Fill(const CampaignAchievementDefinition* d,const CampaignAchievementStateEntry* e,
                const CampaignStatisticsSnapshot* s,CampaignAchievementStatus* out){
    uint32_t value=0;
    if(!d||!e||!s||!out||out->size<sizeof(*out)||!MetricValue(s,d->metric,&value))return 0;
    out->size=sizeof(*out);out->achievement_id=d->achievement_id;out->metric=d->metric;
    out->compare=d->compare;out->threshold=d->threshold;out->current_value=value;
    out->completed=e->completed;out->unlocked_day_key=e->unlocked_day_key;return 1;
}
int CampaignAchievementsGetStatus(int32_t id,CampaignAchievementStatus* out){
    CampaignStatisticsSnapshot stats;const CampaignAchievementDefinition* d;CampaignAchievementStateEntry* e;int ok;
    if(!out||out->size<sizeof(*out)||!CampaignAchievementsEnsureLoaded())return 0;
    CampaignAchievementsRefresh();AchZero(&stats,sizeof(stats));stats.size=sizeof(stats);
    if(!CampaignStatisticsGet(&stats))return 0;
    AchLock();d=CampaignAchievementCatalogFind(id);e=StateFind(id);ok=Fill(d,e,&stats,out);AchUnlock();return ok;
}
int CampaignAchievementsGetStatusByIndex(uint32_t index,CampaignAchievementStatus* out){
    const CampaignAchievementDefinition* d=CampaignAchievementCatalogGet(index);
    return d?CampaignAchievementsGetStatus(d->achievement_id,out):0;
}
int CampaignAchievementsResetState(void){
    int ok;AchLock();AchZero(&g_state,sizeof(g_state));AchZero(&g_load,sizeof(g_load));
    InterlockedExchange(&g_state_loaded,0);if(!BuildPaths()){AchUnlock();return 0;}
    ok=DeleteFileW(g_state_path)||GetLastError()==ERROR_FILE_NOT_FOUND;DeleteFileW(g_state_tmp);
    AchUnlock();return ok?1:0;
}
