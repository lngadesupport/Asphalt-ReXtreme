#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignActivityContext.h"

#define RXAC_MAGIC 0x43415852u /* RXAC */

typedef struct CampaignActivityContextFile {
    uint32_t magic;
    CampaignActivityContext context;
    uint32_t checksum;
} CampaignActivityContextFile;

static CampaignActivityContextFile g_file;
static CampaignActivityContextFile g_load;
static volatile LONG g_lock;
static WCHAR g_path[1024];
static WCHAR g_tmp[1024];
static WCHAR g_exe[1024];
static WCHAR g_dir[1024];

static void AcZero(void* p,uint32_t n){
    volatile unsigned char* q=(volatile unsigned char*)p;uint32_t i;
    for(i=0;i<n;++i)q[i]=0;
}
static void AcCopy(void* d0,const void* s0,uint32_t n){
    volatile unsigned char* d=(volatile unsigned char*)d0;
    const volatile unsigned char* s=(const volatile unsigned char*)s0;uint32_t i;
    for(i=0;i<n;++i)d[i]=s[i];
}
static uint32_t AcHash(const void* p,uint32_t n){
    const unsigned char* s=(const unsigned char*)p;uint32_t h=2166136261u,i;
    for(i=0;i<n;++i){h^=s[i];h*=16777619u;}return h;
}
static void AcLock(void){while(InterlockedCompareExchange(&g_lock,1,0)!=0)Sleep(0);}
static void AcUnlock(void){InterlockedExchange(&g_lock,0);}
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
    AcZero(g_exe,sizeof(g_exe));AcZero(g_dir,sizeof(g_dir));
    n=GetModuleFileNameW(0,g_exe,1024);
    if(n==0||n>=1024)return 0;
    i=(int)n-1;while(i>=0&&g_exe[i]!=L'\\'&&g_exe[i]!=L'/')--i;
    if(i<0)return 0;g_exe[i+1]=0;
    if(!Append(g_dir,1024,g_exe)||!Append(g_dir,1024,L"UserData"))return 0;
    if(!EnsureDir(g_dir))return 0;
    if(!Append(g_dir,1024,L"\\CampaignEdition"))return 0;
    if(!EnsureDir(g_dir))return 0;
    if(!Append(g_path,1024,g_dir)||!Append(g_path,1024,L"\\ActivityContext.dat"))return 0;
    if(!Append(g_tmp,1024,g_dir)||!Append(g_tmp,1024,L"\\ActivityContext.tmp"))return 0;
    return 1;
}
static uint32_t Checksum(const CampaignActivityContextFile* f){
    return AcHash(f,(uint32_t)sizeof(*f)-(uint32_t)sizeof(uint32_t));
}
static int ContextValid(const CampaignActivityContext* c){
    if(!c||c->size!=(uint32_t)sizeof(*c)||
       c->version!=CAMPAIGN_ACTIVITY_CONTEXT_VERSION||
       c->session_id==0||c->activity_id<=0||c->event_id<=0)return 0;
    if(c->activity_type!=CAMPAIGN_ACTIVITY_SPECIAL_EVENT&&
       c->activity_type!=CAMPAIGN_ACTIVITY_CHAMPIONSHIP)return 0;
    if(c->slot_index>=16u)return 0;
    if(c->result_valid>1)return 0;
    if(c->result_valid&&(c->result_placement<=0||c->result_placement>7))return 0;
    if(!c->result_valid&&c->result_placement!=0)return 0;
    return 1;
}
static int FileValid(const CampaignActivityContextFile* f){
    return f&&f->magic==RXAC_MAGIC&&
           f->checksum==Checksum(f)&&ContextValid(&f->context);
}
static int WriteUnlocked(void){
    HANDLE h;DWORD written=0;
    if(!BuildPaths())return 0;
    g_file.magic=RXAC_MAGIC;
    g_file.checksum=Checksum(&g_file);
    DeleteFileW(g_tmp);
    h=CreateFileW(g_tmp,GENERIC_WRITE,FILE_SHARE_READ,0,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE)return 0;
    if(!WriteFile(h,&g_file,sizeof(g_file),&written,0)||written!=sizeof(g_file)){
        CloseHandle(h);DeleteFileW(g_tmp);return 0;
    }
    FlushFileBuffers(h);CloseHandle(h);
    if(!MoveFileExW(g_tmp,g_path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)){
        DeleteFileW(g_tmp);return 0;
    }
    return 1;
}
static int ReadUnlocked(void){
    HANDLE h;DWORD got=0;
    if(!BuildPaths())return 0;
    AcZero(&g_load,sizeof(g_load));
    h=CreateFileW(g_path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,0,
                  OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE)return 0;
    if(!ReadFile(h,&g_load,sizeof(g_load),&got,0)||got!=sizeof(g_load)||!FileValid(&g_load)){
        CloseHandle(h);return 0;
    }
    CloseHandle(h);AcCopy(&g_file,&g_load,sizeof(g_file));return 1;
}

int CampaignActivityContextSet(const CampaignActivityContext* c){
    int ok;
    if(!ContextValid(c))return 0;
    AcLock();AcZero(&g_file,sizeof(g_file));
    g_file.magic=RXAC_MAGIC;AcCopy(&g_file.context,c,sizeof(*c));
    ok=WriteUnlocked();AcUnlock();return ok;
}
int CampaignActivityContextGet(CampaignActivityContext* out){
    int ok;
    if(!out||out->size<(uint32_t)sizeof(*out))return 0;
    AcLock();ok=ReadUnlocked();
    if(ok)AcCopy(out,&g_file.context,sizeof(*out));
    AcUnlock();return ok;
}
int CampaignActivityContextSetResult(uint32_t session_id,int32_t placement){
    int ok=0;
    if(session_id==0||placement<=0||placement>7)return 0;
    AcLock();
    if(ReadUnlocked()&&g_file.context.session_id==session_id){
        g_file.context.result_placement=placement;
        g_file.context.result_valid=1;
        ok=WriteUnlocked();
    }
    AcUnlock();return ok;
}
int CampaignActivityContextClear(uint32_t session_id){
    int ok=1;
    AcLock();
    if(!BuildPaths()){AcUnlock();return 0;}
    if(GetFileAttributesW(g_path)!=INVALID_FILE_ATTRIBUTES){
        if(session_id!=0){
            if(!ReadUnlocked()||g_file.context.session_id!=session_id){AcUnlock();return 0;}
        }
        ok=DeleteFileW(g_path)?1:0;
    }
    DeleteFileW(g_tmp);AcZero(&g_file,sizeof(g_file));AcZero(&g_load,sizeof(g_load));
    AcUnlock();return ok;
}
int CampaignActivityContextReset(void){
    return CampaignActivityContextClear(0);
}
