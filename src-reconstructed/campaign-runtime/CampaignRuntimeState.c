#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignRuntimeState.h"
#include "../campaign-core/CampaignCatalog.h"

#define RUNTIME_MAGIC 0x31525843u /* CXR1 */
#define RUNTIME_VERSION 1u
#define DEFAULT_CREDITS 50000
#define DEFAULT_PREMIUM 0

typedef struct CampaignRuntimeState {
    uint32_t magic;
    uint32_t version;
    uint32_t revision;
    uint32_t flags;

    int32_t credits;
    int32_t premium;
    int32_t selected_car_id;
    int32_t tutorial_step;
    int32_t current_event_id;

    uint32_t owned_count;
    int32_t owned_car_ids[CAMPAIGN_RUNTIME_MAX_OWNED];

    uint32_t checksum;
} CampaignRuntimeState;

static CampaignRuntimeState g_state;
static volatile LONG g_lock;
static volatile LONG g_loaded;
static WCHAR g_dir[1024];
static WCHAR g_path[1024];
static WCHAR g_tmp[1024];

static void Lock(void) {
    while (InterlockedCompareExchange(&g_lock,1,0)!=0) Sleep(0);
}
static void Unlock(void) { InterlockedExchange(&g_lock,0); }

static void Zero(void* p,uint32_t n) {
    volatile unsigned char* q=(volatile unsigned char*)p;
    uint32_t i;
    for(i=0;i<n;++i) q[i]=0;
}
static uint32_t WLen(const WCHAR* s) {
    uint32_t n=0; while(s && s[n]) ++n; return n;
}
static int WAppend(WCHAR* dst,uint32_t cap,const WCHAR* src) {
    uint32_t a=WLen(dst),b=0;
    while(src && src[b]) {
        if(a+b+1>=cap) return 0;
        dst[a+b]=src[b++];
    }
    dst[a+b]=0;
    return 1;
}
static uint32_t Fnv1a(const unsigned char* p,uint32_t n) {
    uint32_t h=2166136261u,i;
    for(i=0;i<n;++i){h^=p[i];h*=16777619u;}
    return h;
}
static uint32_t Checksum(const CampaignRuntimeState* s) {
    return Fnv1a((const unsigned char*)s,
        (uint32_t)(sizeof(*s)-sizeof(uint32_t)));
}
static int BuildPaths(void) {
    WCHAR local[512];
    DWORD n;
    Zero(local,(uint32_t)sizeof(local));
    Zero(g_dir,(uint32_t)sizeof(g_dir));
    Zero(g_path,(uint32_t)sizeof(g_path));
    Zero(g_tmp,(uint32_t)sizeof(g_tmp));

    n=GetEnvironmentVariableW(L"LOCALAPPDATA",local,512);
    if(!n || n>=512) return 0;

    if(!WAppend(g_dir,1024,local)) return 0;
    if(!WAppend(g_dir,1024,
        L"\Packages\A278AB0D.AsphaltXtreme_h6adky7gbf63m"
        L"\LocalState\CampaignEdition")) return 0;
    CreateDirectoryW(g_dir,0);

    if(!WAppend(g_path,1024,g_dir)) return 0;
    if(!WAppend(g_path,1024,L"\CampaignRuntimeV1.dat")) return 0;
    if(!WAppend(g_tmp,1024,g_dir)) return 0;
    if(!WAppend(g_tmp,1024,L"\CampaignRuntimeV1.tmp")) return 0;
    return 1;
}
static void DefaultState(void) {
    Zero(&g_state,(uint32_t)sizeof(g_state));
    g_state.magic=RUNTIME_MAGIC;
    g_state.version=RUNTIME_VERSION;
    g_state.revision=1;
    g_state.credits=DEFAULT_CREDITS;
    g_state.premium=DEFAULT_PREMIUM;
    g_state.selected_car_id=-1;
    g_state.tutorial_step=1;
    g_state.current_event_id=-1;
    g_state.checksum=Checksum(&g_state);
}
static int Valid(const CampaignRuntimeState* s) {
    if(!s) return 0;
    if(s->magic!=RUNTIME_MAGIC || s->version!=RUNTIME_VERSION) return 0;
    if(s->owned_count>CAMPAIGN_RUNTIME_MAX_OWNED) return 0;
    return s->checksum==Checksum(s);
}
static int SaveUnlocked(void) {
    HANDLE h;
    DWORD wrote=0;
    g_state.checksum=Checksum(&g_state);
    h=CreateFileW(g_tmp,GENERIC_WRITE,0,0,CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE) return 0;
    if(!WriteFile(h,&g_state,(DWORD)sizeof(g_state),&wrote,0) ||
       wrote!=(DWORD)sizeof(g_state)) {
        CloseHandle(h); DeleteFileW(g_tmp); return 0;
    }
    FlushFileBuffers(h);
    CloseHandle(h);
    if(!MoveFileExW(g_tmp,g_path,
        MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(g_tmp); return 0;
    }
    return 1;
}
static int LoadUnlocked(void) {
    HANDLE h;
    DWORD got=0;
    CampaignRuntimeState tmp;

    if(g_loaded) return 1;
    if(!BuildPaths()) return 0;

    DefaultState();
    h=CreateFileW(g_path,GENERIC_READ,
        FILE_SHARE_READ|FILE_SHARE_WRITE,0,OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,0);
    if(h!=INVALID_HANDLE_VALUE) {
        Zero(&tmp,(uint32_t)sizeof(tmp));
        if(ReadFile(h,&tmp,(DWORD)sizeof(tmp),&got,0) &&
           got==(DWORD)sizeof(tmp) && Valid(&tmp)) {
            g_state=tmp;
        }
        CloseHandle(h);
    }

    if(g_state.selected_car_id<=0) {
        /*
          Runtime owns selection truth.  On a fresh profile choose the first
          locally catalogued vehicle; no original garage structure is read.
        */
        if(CampaignCatalogEnsureLoaded() && CampaignCatalogCount()>0) {
            int32_t probe=1;
            const CampaignVehicleRecipe* r=0;
            /*
              IDs are sparse. Search a bounded positive range for the first
              recipe. This is startup-only and independent of original state.
            */
            for(probe=1;probe<100000;++probe) {
                r=CampaignCatalogFind(probe);
                if(r){g_state.selected_car_id=r->car_id;break;}
            }
        }
    }

    g_loaded=1;
    if(GetFileAttributesW(g_path)==INVALID_FILE_ATTRIBUTES) {
        SaveUnlocked();
    }
    return 1;
}
static int IsOwnedUnlocked(int32_t id) {
    uint32_t i;
    for(i=0;i<g_state.owned_count;++i)
        if(g_state.owned_car_ids[i]==id) return 1;
    return 0;
}
static int AddOwnedUnlocked(int32_t id) {
    if(id<=0 || IsOwnedUnlocked(id)) return id>0;
    if(g_state.owned_count>=CAMPAIGN_RUNTIME_MAX_OWNED) return 0;
    g_state.owned_car_ids[g_state.owned_count++]=id;
    return 1;
}

int __cdecl CampaignRuntimeBoot(void) {
    int ok;
    Lock(); ok=LoadUnlocked(); Unlock(); return ok;
}
int __cdecl CampaignRuntimeRead(CampaignRuntimeSnapshot* out) {
    if(!out || out->size<(uint32_t)sizeof(*out)) return 0;
    Lock();
    if(!LoadUnlocked()){Unlock();return 0;}
    out->revision=g_state.revision;
    out->credits=g_state.credits;
    out->premium=g_state.premium;
    out->selected_car_id=g_state.selected_car_id;
    out->tutorial_step=g_state.tutorial_step;
    out->current_event_id=g_state.current_event_id;
    out->owned_count=g_state.owned_count;
    Unlock();
    return 1;
}
int __cdecl CampaignRuntimeSelectCar(int32_t car_id) {
    int ok=0;
    if(car_id<=0) return 0;
    Lock();
    if(LoadUnlocked()) {
        g_state.selected_car_id=car_id;
        ++g_state.revision;
        ok=SaveUnlocked();
    }
    Unlock(); return ok;
}
int __cdecl CampaignRuntimeIsOwned(int32_t car_id) {
    int out=0;
    Lock();
    if(LoadUnlocked()) out=IsOwnedUnlocked(car_id);
    Unlock(); return out;
}
int __cdecl CampaignRuntimeBuildSelected(void) {
    const CampaignVehicleRecipe* recipe;
    int id,ok=0;
    Lock();
    if(!LoadUnlocked()){Unlock();return 0;}
    id=g_state.selected_car_id;
    if(id<=0){Unlock();return 0;}
    if(IsOwnedUnlocked(id)){Unlock();return 1;}

    recipe=CampaignCatalogFind(id);
    if(!recipe){Unlock();return 0;}

    /*
      New local acquisition rules.  The first owned car is the tutorial
      starter and is free. Later credit/premium/free recipes are handled
      locally. Blueprint inventory will be implemented in this runtime, not
      delegated to original code.
    */
    if(g_state.owned_count==0) {
        ok=AddOwnedUnlocked(id);
    } else if(recipe->acquisition_type==CAMPAIGN_ACQUIRE_FREE) {
        ok=AddOwnedUnlocked(id);
    } else if(recipe->acquisition_type==CAMPAIGN_ACQUIRE_CREDITS &&
              g_state.credits>=recipe->cost) {
        g_state.credits-=recipe->cost;
        ok=AddOwnedUnlocked(id);
    } else if(recipe->acquisition_type==CAMPAIGN_ACQUIRE_PREMIUM &&
              g_state.premium>=recipe->cost) {
        g_state.premium-=recipe->cost;
        ok=AddOwnedUnlocked(id);
    }

    if(ok) {
        if(g_state.tutorial_step==1) g_state.tutorial_step=2;
        ++g_state.revision;
        ok=SaveUnlocked();
    }
    Unlock(); return ok;
}
int __cdecl CampaignRuntimeSetTutorialStep(int32_t step) {
    int ok=0;
    if(step<0) return 0;
    Lock();
    if(LoadUnlocked()) {
        g_state.tutorial_step=step;
        ++g_state.revision;
        ok=SaveUnlocked();
    }
    Unlock(); return ok;
}
int __cdecl CampaignRuntimeSave(void) {
    int ok;
    Lock(); if(!LoadUnlocked()){Unlock();return 0;}
    ok=SaveUnlocked(); Unlock(); return ok;
}
