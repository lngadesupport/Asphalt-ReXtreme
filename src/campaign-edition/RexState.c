#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "RexState.h"
#include "RexContent.h"

#define REX_SAVE_MAGIC 0x31564552u /* REV1 */
#define REX_SAVE_VERSION 1u

typedef struct RexSaveData {
    uint32_t magic;
    uint32_t version;
    uint32_t revision;
    uint32_t flags;

    int32_t credits;
    int32_t tokens;
    int32_t selected_car;
    int32_t tutorial_stage;
    int32_t current_event;

    uint32_t owned_count;
    int32_t owned_cars[REX_CAMPAIGN_MAX_CARS];

    uint32_t checksum;
} RexSaveData;

static RexSaveData g_state;
static volatile LONG g_lock;
static volatile LONG g_loaded;
static WCHAR g_dir[1024];
static WCHAR g_file[1024];
static WCHAR g_tmp[1024];

static void lock_state(void) {
    while(InterlockedCompareExchange(&g_lock,1,0)!=0) Sleep(0);
}
static void unlock_state(void) { InterlockedExchange(&g_lock,0); }

static void memzero(void* p,uint32_t n) {
    volatile unsigned char* q=(volatile unsigned char*)p;
    uint32_t i;
    for(i=0;i<n;++i) q[i]=0;
}
static uint32_t wlen(const WCHAR* s) {
    uint32_t n=0;
    while(s && s[n]) ++n;
    return n;
}
static int append(WCHAR* dst,uint32_t cap,const WCHAR* src) {
    uint32_t a=wlen(dst),b=0;
    while(src && src[b]) {
        if(a+b+1>=cap) return 0;
        dst[a+b]=src[b++];
    }
    dst[a+b]=0;
    return 1;
}
static uint32_t hash32(const unsigned char* p,uint32_t n) {
    uint32_t h=2166136261u,i;
    for(i=0;i<n;++i){ h^=p[i]; h*=16777619u; }
    return h;
}
static uint32_t checksum(const RexSaveData* s) {
    return hash32((const unsigned char*)s,
        (uint32_t)(sizeof(*s)-sizeof(uint32_t)));
}
static int build_paths(void) {
    WCHAR local[512];
    DWORD n;
    memzero(local,(uint32_t)sizeof(local));
    memzero(g_dir,(uint32_t)sizeof(g_dir));
    memzero(g_file,(uint32_t)sizeof(g_file));
    memzero(g_tmp,(uint32_t)sizeof(g_tmp));

    n=GetEnvironmentVariableW(L"LOCALAPPDATA",local,512);
    if(!n || n>=512) return 0;

    if(!append(g_dir,1024,local)) return 0;
    if(!append(g_dir,1024,
        L"\\Packages\\A278AB0D.AsphaltXtreme_h6adky7gbf63m"
        L"\\LocalState\\CampaignEdition")) return 0;
    CreateDirectoryW(g_dir,0);

    if(!append(g_file,1024,g_dir)) return 0;
    if(!append(g_file,1024,L"\\CampaignStateV1.dat")) return 0;

    if(!append(g_tmp,1024,g_dir)) return 0;
    if(!append(g_tmp,1024,L"\\CampaignStateV1.tmp")) return 0;
    return 1;
}
static void defaults(void) {
    RexContentDefaults content_defaults;

    memzero(&g_state,(uint32_t)sizeof(g_state));
    memzero(&content_defaults,(uint32_t)sizeof(content_defaults));

    g_state.magic=REX_SAVE_MAGIC;
    g_state.version=REX_SAVE_VERSION;
    g_state.revision=1;
    g_state.credits=0;
    g_state.tokens=0;
    g_state.selected_car=-1;
    g_state.tutorial_stage=1;
    g_state.current_event=-1;

    if(RexContentDefaultsRead(&content_defaults)) {
        g_state.credits=content_defaults.starting_credits;
        g_state.tokens=content_defaults.starting_tokens;
        g_state.selected_car=content_defaults.starter_car_id;
    }

    g_state.checksum=checksum(&g_state);
}
static int save_unlocked(void) {
    HANDLE h;
    DWORD wrote=0;
    g_state.checksum=checksum(&g_state);

    h=CreateFileW(g_tmp,GENERIC_WRITE,0,0,CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE) return 0;

    if(!WriteFile(h,&g_state,(DWORD)sizeof(g_state),&wrote,0) ||
       wrote!=(DWORD)sizeof(g_state)) {
        CloseHandle(h);
        DeleteFileW(g_tmp);
        return 0;
    }
    FlushFileBuffers(h);
    CloseHandle(h);

    if(!MoveFileExW(g_tmp,g_file,
        MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(g_tmp);
        return 0;
    }
    return 1;
}
static int is_owned_unlocked(int32_t car_id) {
    uint32_t i;
    for(i=0;i<g_state.owned_count;++i) {
        if(g_state.owned_cars[i]==car_id) return 1;
    }
    return 0;
}
static int add_owned_unlocked(int32_t car_id) {
    if(car_id<=0) return 0;
    if(is_owned_unlocked(car_id)) return 1;
    if(g_state.owned_count>=REX_CAMPAIGN_MAX_CARS) return 0;
    g_state.owned_cars[g_state.owned_count++]=car_id;
    return 1;
}
static int valid(const RexSaveData* s) {
    if(!s) return 0;
    if(s->magic!=REX_SAVE_MAGIC || s->version!=REX_SAVE_VERSION) return 0;
    if(s->owned_count>REX_CAMPAIGN_MAX_CARS) return 0;
    return s->checksum==checksum(s);
}
static int load_unlocked(void) {
    HANDLE h;
    DWORD got=0;
    RexSaveData tmp;

    if(g_loaded) return 1;
    if(!build_paths()) return 0;

    defaults();
    h=CreateFileW(g_file,GENERIC_READ,FILE_SHARE_READ,0,OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,0);

    if(h!=INVALID_HANDLE_VALUE) {
        memzero(&tmp,(uint32_t)sizeof(tmp));
        if(ReadFile(h,&tmp,(DWORD)sizeof(tmp),&got,0) &&
           got==(DWORD)sizeof(tmp) &&
           valid(&tmp)) {
            g_state=tmp;
        }
        CloseHandle(h);
    }

    g_loaded=1;
    if(GetFileAttributesW(g_file)==INVALID_FILE_ATTRIBUTES) {
        save_unlocked();
    }
    return 1;
}
static void make_view_unlocked(RexViewState* out) {
    int owned;
    if(!out) return;

    owned=(g_state.selected_car>0) ?
        is_owned_unlocked(g_state.selected_car) : 0;

    out->revision=g_state.revision;
    out->credits=g_state.credits;
    out->tokens=g_state.tokens;
    out->selected_car=g_state.selected_car;
    out->selected_car_owned=owned;
    out->garage_visual_mode=
        owned ? REX_GARAGE_OWNED : REX_GARAGE_BUILD;
    out->garage_action_enabled=
        (g_state.selected_car>0 && !owned) ? 1 : 0;
    out->garage_busy=0;
    out->tutorial_stage=g_state.tutorial_stage;
    out->current_event=g_state.current_event;
}

int __cdecl RexStateBoot(void) {
    int ok;
    lock_state();
    ok=load_unlocked();
    unlock_state();
    return ok;
}

int __cdecl RexStateRead(RexViewState* out) {
    if(!out || out->size<(uint32_t)sizeof(*out)) return 0;
    lock_state();
    if(!load_unlocked()){ unlock_state(); return 0; }
    make_view_unlocked(out);
    unlock_state();
    return 1;
}

int __cdecl RexStateSelectCar(int32_t car_id) {
    int ok=0;
    if(car_id<=0 || !RexContentFindCar(car_id)) return 0;

    lock_state();
    if(load_unlocked()) {
        g_state.selected_car=car_id;
        ++g_state.revision;
        ok=save_unlocked();
    }
    unlock_state();
    return ok;
}

int __cdecl RexStateBuildSelected(void) {
    const RexCarDefinition* car;
    int ok=0;
    int32_t id;

    lock_state();
    if(!load_unlocked()){ unlock_state(); return 0; }

    id=g_state.selected_car;
    if(id<=0){ unlock_state(); return 0; }
    if(is_owned_unlocked(id)){ unlock_state(); return 1; }

    car=RexContentFindCar(id);
    if(!car){ unlock_state(); return 0; }

    if(g_state.owned_count==0) {
        ok=add_owned_unlocked(id);
    } else if(car->acquire_mode==REX_ACQUIRE_FREE) {
        ok=add_owned_unlocked(id);
    } else if(car->acquire_mode==REX_ACQUIRE_CREDITS &&
              g_state.credits>=car->price) {
        g_state.credits-=car->price;
        ok=add_owned_unlocked(id);
    } else if(car->acquire_mode==REX_ACQUIRE_TOKENS &&
              g_state.tokens>=car->price) {
        g_state.tokens-=car->price;
        ok=add_owned_unlocked(id);
    }

    if(ok) {
        if(g_state.tutorial_stage==1) g_state.tutorial_stage=2;
        ++g_state.revision;
        ok=save_unlocked();
    }

    unlock_state();
    return ok;
}
