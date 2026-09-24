#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignLastResult.h"

#define RXLR_MAGIC 0x524C5852u /* RXLR */

typedef struct CampaignLastResultFile {
    uint32_t magic;
    CampaignLastResultSnapshot snapshot;
    uint32_t checksum;
} CampaignLastResultFile;

static CampaignLastResultFile g_result;
static CampaignLastResultFile g_load;
static volatile LONG g_loaded;
static volatile LONG g_lock;
static WCHAR g_path[1024];
static WCHAR g_tmp[1024];
static WCHAR g_exe[1024];
static WCHAR g_dir[1024];

static void LrZero(void* p,uint32_t n){
    volatile unsigned char* q=(volatile unsigned char*)p;uint32_t i;
    for(i=0;i<n;++i)q[i]=0;
}
static void LrCopy(void* d0,const void* s0,uint32_t n){
    volatile unsigned char* d=(volatile unsigned char*)d0;
    const volatile unsigned char* s=(const volatile unsigned char*)s0;uint32_t i;
    for(i=0;i<n;++i)d[i]=s[i];
}
static uint32_t LrHash(const void* p,uint32_t n){
    const unsigned char* s=(const unsigned char*)p;uint32_t h=2166136261u,i;
    for(i=0;i<n;++i){h^=s[i];h*=16777619u;}return h;
}
static void LrLock(void){while(InterlockedCompareExchange(&g_lock,1,0)!=0)Sleep(0);}
static void LrUnlock(void){InterlockedExchange(&g_lock,0);}
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
    LrZero(g_exe,sizeof(g_exe));LrZero(g_dir,sizeof(g_dir));
    n=GetModuleFileNameW(0,g_exe,1024);
    if(n==0||n>=1024)return 0;
    i=(int)n-1;while(i>=0&&g_exe[i]!=L'\\'&&g_exe[i]!=L'/')--i;
    if(i<0)return 0;g_exe[i+1]=0;
    if(!Append(g_dir,1024,g_exe)||!Append(g_dir,1024,L"UserData"))return 0;
    if(!EnsureDir(g_dir))return 0;
    if(!Append(g_dir,1024,L"\\CampaignEdition"))return 0;
    if(!EnsureDir(g_dir))return 0;
    if(!Append(g_path,1024,g_dir)||!Append(g_path,1024,L"\\LastRaceResult.dat"))return 0;
    if(!Append(g_tmp,1024,g_dir)||!Append(g_tmp,1024,L"\\LastRaceResult.tmp"))return 0;
    return 1;
}
static uint32_t Checksum(const CampaignLastResultFile* f){
    return LrHash(f,(uint32_t)sizeof(*f)-(uint32_t)sizeof(uint32_t));
}
static int MetricsValid(const CampaignRaceMetrics* m){
    if(!m||m->size!=sizeof(*m)||m->version!=CAMPAIGN_RACE_METRICS_VERSION)return 0;
    if(m->session_id==0||m->placement<=0||m->placement>7||m->finish_time_ms<0)return 0;
    if(m->stars_awarded<0||m->credits_awarded<0||m->premium_awarded<0||m->completion_count<0)return 0;
    return 1;
}
static int Valid(const CampaignLastResultFile* f){
    const CampaignLastResultSnapshot* s;
    if(!f||f->magic!=RXLR_MAGIC||f->checksum!=Checksum(f))return 0;
    s=&f->snapshot;
    if(s->size!=sizeof(*s)||s->version!=CAMPAIGN_LAST_RESULT_VERSION)return 0;
    if(s->event_id<=0||s->car_id<0||s->session_id==0)return 0;
    if(s->metrics.session_id!=s->session_id||!MetricsValid(&s->metrics))return 0;
    return 1;
}
static int WriteUnlocked(void){
    HANDLE h;DWORD written=0;
    if(!BuildPaths())return 0;
    g_result.checksum=Checksum(&g_result);
    DeleteFileW(g_tmp);
    h=CreateFileW(g_tmp,GENERIC_WRITE,FILE_SHARE_READ,0,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE)return 0;
    if(!WriteFile(h,&g_result,sizeof(g_result),&written,0)||written!=sizeof(g_result)){
        CloseHandle(h);DeleteFileW(g_tmp);return 0;
    }
    FlushFileBuffers(h);CloseHandle(h);
    if(!MoveFileExW(g_tmp,g_path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)){
        DeleteFileW(g_tmp);return 0;
    }
    return 1;
}
int CampaignLastResultEnsureLoaded(void){
    HANDLE h;DWORD got=0;
    if(InterlockedCompareExchange(&g_loaded,1,1))return g_result.magic==RXLR_MAGIC?1:0;
    LrLock();
    if(g_loaded){int ok=g_result.magic==RXLR_MAGIC;LrUnlock();return ok;}
    LrZero(&g_result,sizeof(g_result));LrZero(&g_load,sizeof(g_load));
    if(!BuildPaths()){InterlockedExchange(&g_loaded,1);LrUnlock();return 0;}
    h=CreateFileW(g_path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,0,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,0);
    if(h!=INVALID_HANDLE_VALUE){
        if(ReadFile(h,&g_load,sizeof(g_load),&got,0)&&got==sizeof(g_load)&&Valid(&g_load))
            LrCopy(&g_result,&g_load,sizeof(g_result));
        CloseHandle(h);
    }
    InterlockedExchange(&g_loaded,1);
    {
        int ok=g_result.magic==RXLR_MAGIC;
        LrUnlock();return ok;
    }
}
int CampaignLastResultRecord(
    int32_t event_id,
    int32_t car_id,
    const CampaignRaceMetrics* metrics,
    uint32_t campaign_revision
){
    if(event_id<=0||car_id<0||!MetricsValid(metrics))return 0;
    LrLock();
    LrZero(&g_result,sizeof(g_result));
    g_result.magic=RXLR_MAGIC;
    g_result.snapshot.size=sizeof(g_result.snapshot);
    g_result.snapshot.version=CAMPAIGN_LAST_RESULT_VERSION;
    g_result.snapshot.campaign_revision=campaign_revision;
    g_result.snapshot.event_id=event_id;
    g_result.snapshot.car_id=car_id;
    g_result.snapshot.session_id=metrics->session_id;
    LrCopy(&g_result.snapshot.metrics,metrics,sizeof(*metrics));
    InterlockedExchange(&g_loaded,1);
    if(!WriteUnlocked()){LrUnlock();return 0;}
    LrUnlock();return 1;
}
int CampaignLastResultGet(CampaignLastResultSnapshot* out){
    if(!out||out->size<sizeof(*out)||!CampaignLastResultEnsureLoaded())return 0;
    LrLock();LrCopy(out,&g_result.snapshot,sizeof(*out));LrUnlock();return 1;
}
int CampaignLastResultReload(void){
    LrLock();
    LrZero(&g_result,sizeof(g_result));LrZero(&g_load,sizeof(g_load));
    InterlockedExchange(&g_loaded,0);
    LrUnlock();
    return CampaignLastResultEnsureLoaded();
}
int CampaignLastResultClear(void){
    int ok;
    LrLock();
    LrZero(&g_result,sizeof(g_result));LrZero(&g_load,sizeof(g_load));
    InterlockedExchange(&g_loaded,1);
    if(!BuildPaths()){LrUnlock();return 0;}
    ok=DeleteFileW(g_path)||GetLastError()==ERROR_FILE_NOT_FOUND;
    DeleteFileW(g_tmp);LrUnlock();return ok?1:0;
}
