#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignRuntimeCatalog.h"

typedef struct CampaignRuntimeCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignRuntimeRecipe vehicles[CAMPAIGN_RUNTIME_CATALOG_MAX];
    uint32_t checksum;
} CampaignRuntimeCatalogFile;

static CampaignRuntimeCatalogFile g_catalog;
static volatile LONG g_loaded;
static WCHAR g_path[1024];

static void Zero(void* p,uint32_t n) {
    volatile unsigned char* q=(volatile unsigned char*)p;
    uint32_t i; for(i=0;i<n;++i) q[i]=0;
}
static uint32_t Fnv1a(const unsigned char* p,uint32_t n) {
    uint32_t h=2166136261u,i;
    for(i=0;i<n;++i){h^=p[i];h*=16777619u;}
    return h;
}
static uint32_t Checksum(const CampaignRuntimeCatalogFile* f) {
    return Fnv1a((const unsigned char*)f,
        (uint32_t)(sizeof(*f)-sizeof(uint32_t)));
}
static int BuildPath(void) {
    HMODULE self;
    DWORD n;
    uint32_t i,j;
    static const WCHAR name[]=L"CampaignCatalog.dat";

    Zero(g_path,(uint32_t)sizeof(g_path));
    self=GetModuleHandleW(L"IGPLib_x86.dll");
    if(!self) return 0;
    n=GetModuleFileNameW(self,g_path,1024);
    if(!n || n>=1024) return 0;

    i=n;
    while(i>0) {
        --i;
        if(g_path[i]==L'\\' || g_path[i]==L'/'){++i;break;}
    }
    for(j=0;name[j];++j) {
        if(i+j+1>=1024) return 0;
        g_path[i+j]=name[j];
    }
    g_path[i+j]=0;
    return 1;
}
static int Valid(const CampaignRuntimeCatalogFile* f) {
    uint32_t i;
    if(!f) return 0;
    if(f->magic!=CAMPAIGN_RUNTIME_CATALOG_MAGIC ||
       f->version!=CAMPAIGN_RUNTIME_CATALOG_VERSION ||
       f->count>CAMPAIGN_RUNTIME_CATALOG_MAX) return 0;
    if(f->checksum!=Checksum(f)) return 0;
    for(i=0;i<f->count;++i) {
        const CampaignRuntimeRecipe* r=&f->vehicles[i];
        if(r->car_id<=0) return 0;
        if(r->acquisition_type<CAMPAIGN_RUNTIME_ACQUIRE_BLUEPRINT ||
           r->acquisition_type>CAMPAIGN_RUNTIME_ACQUIRE_FREE) return 0;
        if(r->cost<0) return 0;
        if(i && f->vehicles[i-1].car_id>=r->car_id) return 0;
    }
    return 1;
}
int __cdecl CampaignRuntimeCatalogLoad(void) {
    HANDLE h;
    DWORD got=0;
    if(g_loaded) return g_catalog.count>0;
    Zero(&g_catalog,(uint32_t)sizeof(g_catalog));
    if(!BuildPath()){InterlockedExchange(&g_loaded,1);return 0;}
    h=CreateFileW(g_path,GENERIC_READ,
        FILE_SHARE_READ|FILE_SHARE_WRITE,0,OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE){InterlockedExchange(&g_loaded,1);return 0;}
    if(!ReadFile(h,&g_catalog,(DWORD)sizeof(g_catalog),&got,0) ||
       got!=(DWORD)sizeof(g_catalog) || !Valid(&g_catalog)) {
        CloseHandle(h);
        Zero(&g_catalog,(uint32_t)sizeof(g_catalog));
        InterlockedExchange(&g_loaded,1);
        return 0;
    }
    CloseHandle(h);
    InterlockedExchange(&g_loaded,1);
    return 1;
}
const CampaignRuntimeRecipe* __cdecl CampaignRuntimeCatalogFind(int32_t id) {
    int lo,hi;
    if(id<=0 || !CampaignRuntimeCatalogLoad()) return 0;
    lo=0; hi=(int)g_catalog.count-1;
    while(lo<=hi) {
        int mid=lo+((hi-lo)/2);
        int32_t v=g_catalog.vehicles[mid].car_id;
        if(v==id) return &g_catalog.vehicles[mid];
        if(v<id) lo=mid+1; else hi=mid-1;
    }
    return 0;
}
const CampaignRuntimeRecipe* __cdecl CampaignRuntimeCatalogFirst(void) {
    if(!CampaignRuntimeCatalogLoad() || !g_catalog.count) return 0;
    return &g_catalog.vehicles[0];
}
uint32_t __cdecl CampaignRuntimeCatalogCount(void) {
    CampaignRuntimeCatalogLoad();
    return g_catalog.count;
}
