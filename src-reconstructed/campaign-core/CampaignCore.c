#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>

#define CAMPAIGN_MAGIC 0x45435852u
#define CAMPAIGN_VERSION 1u
#define CAMPAIGN_MAX_OWNED 256u
#define CAMPAIGN_MAX_INVENTORY 256u

typedef struct CampaignInventoryEntry { int32_t item_id; int32_t amount; } CampaignInventoryEntry;
typedef struct CampaignState {
    uint32_t magic, version, revision, craft_count;
    int32_t credits, premium_currency, last_car_id;
    uint32_t owned_count;
    int32_t owned_car_ids[CAMPAIGN_MAX_OWNED];
    uint32_t inventory_count;
    CampaignInventoryEntry inventory[CAMPAIGN_MAX_INVENTORY];
    uint32_t checksum;
} CampaignState;

static CampaignState g_state;
static volatile LONG g_lock;
static volatile LONG g_loaded;
static WCHAR g_state_path[1024];
static WCHAR g_campaign_dir[1024];

static void LockState(void){ while(InterlockedCompareExchange(&g_lock,1,0)!=0) Sleep(0); }
static void UnlockState(void){ InterlockedExchange(&g_lock,0); }
static void ZeroBytes(void* p,uint32_t count){ volatile unsigned char* q=(volatile unsigned char*)p; uint32_t i; for(i=0;i<count;++i)q[i]=0; }
static void CopyBytes(void* dst,const void* src,uint32_t count){ volatile unsigned char* d=(volatile unsigned char*)dst; const volatile unsigned char* q=(const volatile unsigned char*)src; uint32_t i; for(i=0;i<count;++i)d[i]=q[i]; }
static uint32_t WideLen(const WCHAR* s){ uint32_t n=0;if(!s)return 0;while(s[n])++n;return n; }
static int WideAppend(WCHAR* dst,uint32_t cap,const WCHAR* src){ uint32_t a=WideLen(dst),b=0;if(!src||a>=cap)return 0;while(src[b]){if(a+b+1>=cap)return 0;dst[a+b]=src[b];++b;}dst[a+b]=0;return 1; }
static uint32_t Fnv1a(const unsigned char* data,uint32_t count){ uint32_t h=2166136261u,i;for(i=0;i<count;++i){h^=data[i];h*=16777619u;}return h; }
static uint32_t StateChecksum(const CampaignState* s){ return Fnv1a((const unsigned char*)s,(uint32_t)(sizeof(CampaignState)-sizeof(uint32_t))); }
static void InitDefaultState(CampaignState* s){ ZeroBytes(s,(uint32_t)sizeof(*s));s->magic=CAMPAIGN_MAGIC;s->version=CAMPAIGN_VERSION;s->revision=1;s->credits=50000;s->last_car_id=-1;s->checksum=StateChecksum(s); }

static int BuildStatePath(void){
    WCHAR local[512],family[256]; UINT32 family_len=256; DWORD n;
    ZeroBytes(local,(uint32_t)sizeof(local));ZeroBytes(family,(uint32_t)sizeof(family));ZeroBytes(g_state_path,(uint32_t)sizeof(g_state_path));ZeroBytes(g_campaign_dir,(uint32_t)sizeof(g_campaign_dir));
    n=GetEnvironmentVariableW(L"LOCALAPPDATA",local,512);if(n==0||n>=512)return 0;
    if(GetCurrentPackageFamilyName(&family_len,family)!=ERROR_SUCCESS)return 0;
    if(!WideAppend(g_campaign_dir,1024,local))return 0;
    if(!WideAppend(g_campaign_dir,1024,L"\\Packages\\"))return 0;
    if(!WideAppend(g_campaign_dir,1024,family))return 0;
    if(!WideAppend(g_campaign_dir,1024,L"\\LocalState\\CampaignEdition"))return 0;
    CreateDirectoryW(g_campaign_dir,0);
    if(!WideAppend(g_state_path,1024,g_campaign_dir))return 0;
    if(!WideAppend(g_state_path,1024,L"\\campaign_state.bin"))return 0;
    return 1;
}

static int SaveStateUnlocked(void){
    HANDLE h;DWORD written=0;
    if(!g_state_path[0]&&!BuildStatePath())return 0;
    g_state.checksum=StateChecksum(&g_state);
    h=CreateFileW(g_state_path,GENERIC_WRITE,FILE_SHARE_READ,0,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE)return 0;
    if(!WriteFile(h,&g_state,(DWORD)sizeof(g_state),&written,0)||written!=(DWORD)sizeof(g_state)){CloseHandle(h);return 0;}
    FlushFileBuffers(h);CloseHandle(h);return 1;
}

static void EnsureLoadedUnlocked(void){
    HANDLE h;DWORD got=0;CampaignState tmp;
    if(g_loaded)return;
    InitDefaultState(&g_state);
    if(BuildStatePath()){
        ZeroBytes(&tmp,(uint32_t)sizeof(tmp));
        h=CreateFileW(g_state_path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,0,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,0);
        if(h!=INVALID_HANDLE_VALUE){
            if(ReadFile(h,&tmp,(DWORD)sizeof(tmp),&got,0)&&got==(DWORD)sizeof(tmp)&&tmp.magic==CAMPAIGN_MAGIC&&tmp.version==CAMPAIGN_VERSION&&tmp.owned_count<=CAMPAIGN_MAX_OWNED&&tmp.inventory_count<=CAMPAIGN_MAX_INVENTORY&&tmp.checksum==StateChecksum(&tmp))CopyBytes(&g_state,&tmp,(uint32_t)sizeof(tmp));
            CloseHandle(h);
        }else SaveStateUnlocked();
    }
    InterlockedExchange(&g_loaded,1);
}

static int IsOwnedUnlocked(int32_t car_id){ uint32_t i;if(car_id<=0)return 0;for(i=0;i<g_state.owned_count;++i)if(g_state.owned_car_ids[i]==car_id)return 1;return 0; }
static int AddOwnedUnlocked(int32_t car_id){ if(IsOwnedUnlocked(car_id))return 1;if(g_state.owned_count>=CAMPAIGN_MAX_OWNED)return 0;g_state.owned_car_ids[g_state.owned_count++]=car_id;g_state.last_car_id=car_id;++g_state.craft_count;++g_state.revision;return SaveStateUnlocked(); }

static int ResolveSelectedCarId(void* garage){
    unsigned char* gs=(unsigned char*)garage;void* holder;void* selected;
    if(!gs)return -1;
    holder=*(void**)(gs+0x2D4);if(!holder)return -1;
    selected=*(void**)holder;if(!selected)return -1;
    return *(int32_t*)((unsigned char*)selected+0xC0);
}

static void RefreshGarageUi(void* garage){
    void*** obj=(void***)garage;void** vt;void (__thiscall *refresh)(void*);
    if(!obj)return;vt=*obj;if(!vt)return;
    refresh=(void (__thiscall *)(void*))vt[0x50/4];
    if(refresh)refresh(garage);
}

int __cdecl CampaignIsOwned(int32_t car_id){ int result;LockState();EnsureLoadedUnlocked();result=IsOwnedUnlocked(car_id);UnlockState();return result; }
int __cdecl CampaignCraftInvoke(void* garage){ int32_t id=ResolveSelectedCarId(garage);int ok;if(id<=0)return 0;LockState();EnsureLoadedUnlocked();ok=AddOwnedUnlocked(id);UnlockState();if(ok)RefreshGarageUi(garage);return ok; }
