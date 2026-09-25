#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "RexContent.h"

#define REX_CONTENT_MAGIC 0x31434552u /* REC1 */
#define REX_CONTENT_VERSION 1u

typedef struct RexContentFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    RexCarDefinition cars[REX_CONTENT_MAX_CARS];
    uint32_t checksum;
} RexContentFile;

static RexContentFile g_content;
static volatile LONG g_loaded;
static WCHAR g_path[1024];

static void memzero(void* p, uint32_t n) {
    volatile unsigned char* q=(volatile unsigned char*)p;
    uint32_t i;
    for(i=0;i<n;++i) q[i]=0;
}
static uint32_t hash32(const unsigned char* p,uint32_t n) {
    uint32_t h=2166136261u,i;
    for(i=0;i<n;++i){ h^=p[i]; h*=16777619u; }
    return h;
}
static uint32_t calc_checksum(const RexContentFile* f) {
    return hash32((const unsigned char*)f,
        (uint32_t)(sizeof(*f)-sizeof(uint32_t)));
}
static int build_path(void) {
    HMODULE self;
    DWORD n;
    uint32_t i,j;
    static const WCHAR file_name[]=L"CampaignContentV1.dat";

    memzero(g_path,(uint32_t)sizeof(g_path));
    self=GetModuleHandleW(L"IGPLib_x86.dll");
    if(!self) return 0;

    n=GetModuleFileNameW(self,g_path,1024);
    if(!n || n>=1024) return 0;

    i=n;
    while(i>0) {
        --i;
        if(g_path[i]==L'\\' || g_path[i]==L'/'){ ++i; break; }
    }
    for(j=0;file_name[j];++j) {
        if(i+j+1>=1024) return 0;
        g_path[i+j]=file_name[j];
    }
    g_path[i+j]=0;
    return 1;
}
static int valid(const RexContentFile* f) {
    uint32_t i;
    if(!f) return 0;
    if(f->magic!=REX_CONTENT_MAGIC ||
       f->version!=REX_CONTENT_VERSION ||
       f->count==0 ||
       f->count>REX_CONTENT_MAX_CARS) return 0;
    if(f->checksum!=calc_checksum(f)) return 0;
    for(i=0;i<f->count;++i) {
        if(f->cars[i].car_id<=0) return 0;
        if(f->cars[i].acquire_mode<REX_ACQUIRE_FREE ||
           f->cars[i].acquire_mode>REX_ACQUIRE_TOKENS) return 0;
        if(f->cars[i].price<0) return 0;
        if(i && f->cars[i-1].car_id>=f->cars[i].car_id) return 0;
    }
    return 1;
}

int __cdecl RexContentLoad(void) {
    HANDLE h;
    DWORD got=0;
    if(g_loaded) return g_content.count>0;

    memzero(&g_content,(uint32_t)sizeof(g_content));
    if(!build_path()){ InterlockedExchange(&g_loaded,1); return 0; }

    h=CreateFileW(g_path,GENERIC_READ,FILE_SHARE_READ,0,OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE){ InterlockedExchange(&g_loaded,1); return 0; }

    if(!ReadFile(h,&g_content,(DWORD)sizeof(g_content),&got,0) ||
       got!=(DWORD)sizeof(g_content) ||
       !valid(&g_content)) {
        CloseHandle(h);
        memzero(&g_content,(uint32_t)sizeof(g_content));
        InterlockedExchange(&g_loaded,1);
        return 0;
    }

    CloseHandle(h);
    InterlockedExchange(&g_loaded,1);
    return 1;
}

uint32_t __cdecl RexContentCarCount(void) {
    RexContentLoad();
    return g_content.count;
}

const RexCarDefinition* __cdecl RexContentFirstCar(void) {
    if(!RexContentLoad() || !g_content.count) return 0;
    return &g_content.cars[0];
}

const RexCarDefinition* __cdecl RexContentFindCar(int32_t car_id) {
    int lo,hi;
    if(car_id<=0 || !RexContentLoad()) return 0;
    lo=0;
    hi=(int)g_content.count-1;

    while(lo<=hi) {
        int mid=lo+((hi-lo)/2);
        int32_t id=g_content.cars[mid].car_id;
        if(id==car_id) return &g_content.cars[mid];
        if(id<car_id) lo=mid+1;
        else hi=mid-1;
    }
    return 0;
}
