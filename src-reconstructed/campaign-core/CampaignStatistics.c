#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignStatistics.h"

#define RXST_MAGIC 0x54535852u /* RXST */

typedef struct CampaignStatisticsFile {
    uint32_t magic;
    CampaignStatisticsSnapshot stats;
    uint32_t checksum;
} CampaignStatisticsFile;

static CampaignStatisticsFile g_stats;
static CampaignStatisticsFile g_stats_load;
static volatile LONG g_loaded;
static volatile LONG g_lock;
static WCHAR g_path[1024];
static WCHAR g_tmp[1024];
static WCHAR g_exe_path[1024];
static WCHAR g_campaign_dir[1024];

static void StatsZero(void* p, uint32_t n) {
    volatile unsigned char* q=(volatile unsigned char*)p;
    uint32_t i;
    for(i=0;i<n;++i) q[i]=0;
}

static void StatsCopy(void* d0,const void* s0,uint32_t n) {
    volatile unsigned char* d=(volatile unsigned char*)d0;
    const volatile unsigned char* s=(const volatile unsigned char*)s0;
    uint32_t i;
    for(i=0;i<n;++i) d[i]=s[i];
}

static uint32_t StatsHash(const void* p,uint32_t n) {
    const unsigned char* s=(const unsigned char*)p;
    uint32_t h=2166136261u,i;
    for(i=0;i<n;++i){h^=s[i];h*=16777619u;}
    return h;
}

static void StatsLock(void){while(InterlockedCompareExchange(&g_lock,1,0)!=0) Sleep(0);}
static void StatsUnlock(void){InterlockedExchange(&g_lock,0);}

static int WideAppend(WCHAR* dst,uint32_t cap,const WCHAR* src){
    uint32_t n=0,i=0;
    if(!dst||!src||cap==0)return 0;
    while(dst[n]){++n;if(n>=cap)return 0;}
    while(src[i]){if(n+1>=cap)return 0;dst[n++]=src[i++];}
    dst[n]=0;return 1;
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
    StatsZero(g_exe_path,sizeof(g_exe_path));
    StatsZero(g_campaign_dir,sizeof(g_campaign_dir));
    n=GetModuleFileNameW(0,g_exe_path,1024);
    if(n==0||n>=1024)return 0;
    i=(int)n-1;while(i>=0&&g_exe_path[i]!=L'\\'&&g_exe_path[i]!=L'/')--i;
    if(i<0)return 0;g_exe_path[i+1]=0;

    if(!WideAppend(g_campaign_dir,1024,g_exe_path)||
       !WideAppend(g_campaign_dir,1024,L"UserData"))return 0;
    if(!EnsureDir(g_campaign_dir))return 0;
    if(!WideAppend(g_campaign_dir,1024,L"\\CampaignEdition"))return 0;
    if(!EnsureDir(g_campaign_dir))return 0;

    if(!WideAppend(g_path,1024,g_campaign_dir)||
       !WideAppend(g_path,1024,L"\\CampaignStatistics.dat"))return 0;
    if(!WideAppend(g_tmp,1024,g_campaign_dir)||
       !WideAppend(g_tmp,1024,L"\\CampaignStatistics.tmp"))return 0;
    return 1;
}

static uint32_t Checksum(const CampaignStatisticsFile* f){
    return StatsHash(f,(uint32_t)sizeof(*f)-(uint32_t)sizeof(uint32_t));
}

static void Init(void){
    StatsZero(&g_stats,sizeof(g_stats));
    g_stats.magic=RXST_MAGIC;
    g_stats.stats.size=sizeof(g_stats.stats);
    g_stats.stats.version=CAMPAIGN_STATISTICS_VERSION;
    g_stats.stats.revision=1;
}

static int Valid(const CampaignStatisticsFile* f){
    const CampaignStatisticsSnapshot* s;
    if(!f||f->magic!=RXST_MAGIC||f->checksum!=Checksum(f))return 0;
    s=&f->stats;
    if(s->size!=sizeof(*s)||s->version!=CAMPAIGN_STATISTICS_VERSION)return 0;
    if(s->wins>s->races_with_metrics||s->podiums>s->races_with_metrics)return 0;
    if(s->best_placement>7)return 0;
    return 1;
}

static int WriteUnlocked(void){
    HANDLE h;DWORD written=0;
    if(!BuildPaths())return 0;
    g_stats.checksum=Checksum(&g_stats);
    DeleteFileW(g_tmp);
    h=CreateFileW(g_tmp,GENERIC_WRITE,FILE_SHARE_READ,0,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE)return 0;
    if(!WriteFile(h,&g_stats,sizeof(g_stats),&written,0)||written!=sizeof(g_stats)){
        CloseHandle(h);DeleteFileW(g_tmp);return 0;
    }
    FlushFileBuffers(h);CloseHandle(h);
    if(!MoveFileExW(g_tmp,g_path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)){
        DeleteFileW(g_tmp);return 0;
    }
    return 1;
}

int CampaignStatisticsEnsureLoaded(void){
    HANDLE h;DWORD got=0;
    if(InterlockedCompareExchange(&g_loaded,1,1))return 1;
    StatsLock();
    if(g_loaded){StatsUnlock();return 1;}
    Init();
    if(!BuildPaths()){StatsUnlock();return 0;}
    h=CreateFileW(g_path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,0,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,0);
    if(h!=INVALID_HANDLE_VALUE){
        StatsZero(&g_stats_load,sizeof(g_stats_load));
        if(ReadFile(h,&g_stats_load,sizeof(g_stats_load),&got,0)&&got==sizeof(g_stats_load)&&Valid(&g_stats_load)){
            StatsCopy(&g_stats,&g_stats_load,sizeof(g_stats));
        }
        CloseHandle(h);
    }
    InterlockedExchange(&g_loaded,1);
    if(GetFileAttributesW(g_path)==INVALID_FILE_ATTRIBUTES&&!WriteUnlocked()){
        StatsUnlock();return 0;
    }
    StatsUnlock();return 1;
}

static uint32_t AddSat(uint32_t a,uint32_t b){
    if(a>0xFFFFFFFFu-b)return 0xFFFFFFFFu;
    return a+b;
}

static uint32_t MetricU32(int32_t value){return value>0?(uint32_t)value:0u;}

int CampaignStatisticsRecordRace(const CampaignRaceMetrics* m){
    if(!m||m->size<sizeof(*m)||m->version!=CAMPAIGN_RACE_METRICS_VERSION||
       m->placement<=0||m->placement>7||m->finish_time_ms<0)return 0;
    if(!CampaignStatisticsEnsureLoaded())return 0;

    StatsLock();
    g_stats.stats.races_with_metrics=AddSat(g_stats.stats.races_with_metrics,1);
    if(m->placement==1)g_stats.stats.wins=AddSat(g_stats.stats.wins,1);
    if(m->placement<=3)g_stats.stats.podiums=AddSat(g_stats.stats.podiums,1);
    if(g_stats.stats.best_placement==0||(uint32_t)m->placement<g_stats.stats.best_placement)
        g_stats.stats.best_placement=(uint32_t)m->placement;
    if(m->finish_time_ms>0&&(g_stats.stats.best_finish_time_ms==0||
       (uint32_t)m->finish_time_ms<g_stats.stats.best_finish_time_ms))
        g_stats.stats.best_finish_time_ms=(uint32_t)m->finish_time_ms;

    g_stats.stats.total_drift_meters=AddSat(g_stats.stats.total_drift_meters,MetricU32(m->drift_meters));
    g_stats.stats.total_air_time_ms=AddSat(g_stats.stats.total_air_time_ms,MetricU32(m->air_time_ms));
    g_stats.stats.total_nitro_time_ms=AddSat(g_stats.stats.total_nitro_time_ms,MetricU32(m->nitro_time_ms));
    g_stats.stats.total_wrecked_cars=AddSat(g_stats.stats.total_wrecked_cars,MetricU32(m->wrecked_cars));
    g_stats.stats.total_wrecked_environment=AddSat(g_stats.stats.total_wrecked_environment,MetricU32(m->wrecked_environment));
    g_stats.stats.total_wrecks_made=AddSat(g_stats.stats.total_wrecks_made,MetricU32(m->wrecks_made));
    g_stats.stats.total_flat_spins=AddSat(g_stats.stats.total_flat_spins,MetricU32(m->flat_spins));
    g_stats.stats.total_barrel_rolls=AddSat(g_stats.stats.total_barrel_rolls,MetricU32(m->barrel_rolls));
    g_stats.stats.total_obstacles_broken=AddSat(g_stats.stats.total_obstacles_broken,MetricU32(m->obstacles_broken));
    g_stats.stats.total_nitro_all_in=AddSat(g_stats.stats.total_nitro_all_in,MetricU32(m->nitro_all_in));
    g_stats.stats.total_nitro_chain=AddSat(g_stats.stats.total_nitro_chain,MetricU32(m->nitro_chain));
    g_stats.stats.total_nitro_normal=AddSat(g_stats.stats.total_nitro_normal,MetricU32(m->nitro_normal));
    ++g_stats.stats.revision;
    if(!WriteUnlocked()){StatsUnlock();return 0;}
    StatsUnlock();return 1;
}

int CampaignStatisticsGet(CampaignStatisticsSnapshot* out){
    if(!out||out->size<sizeof(*out)||!CampaignStatisticsEnsureLoaded())return 0;
    StatsLock();StatsCopy(out,&g_stats.stats,sizeof(*out));StatsUnlock();return 1;
}

int CampaignStatisticsReset(void){
    int ok;
    StatsLock();Init();InterlockedExchange(&g_loaded,1);
    if(!BuildPaths()){StatsUnlock();return 0;}
    ok=DeleteFileW(g_path)||GetLastError()==ERROR_FILE_NOT_FOUND;
    DeleteFileW(g_tmp);
    if(ok)ok=WriteUnlocked();
    StatsUnlock();return ok?1:0;
}
