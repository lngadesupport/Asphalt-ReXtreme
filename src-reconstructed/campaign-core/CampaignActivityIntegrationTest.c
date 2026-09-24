#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignCore.h"
#include "CampaignEventCatalog.h"
#include "CampaignSpecialEventCatalog.h"
#include "CampaignChampionshipCatalog.h"
#include "CampaignActivityContext.h"
#include "CampaignSeasonCatalog.h"

typedef struct EventCatalogFile {
    uint32_t magic,version,count,reserved;
    CampaignEventDefinition events[CAMPAIGN_EVENT_CATALOG_MAX_EVENTS];
    uint32_t checksum;
} EventCatalogFile;

typedef struct SpecialCatalogFile {
    uint32_t magic,version,count,reserved;
    CampaignSpecialEventDefinition entries[CAMPAIGN_SPECIAL_EVENT_MAX];
    uint32_t checksum;
} SpecialCatalogFile;

typedef struct ChampionshipCatalogFile {
    uint32_t magic,version,count,reserved;
    CampaignChampionshipDefinition entries[CAMPAIGN_CHAMPIONSHIP_MAX];
    uint32_t checksum;
} ChampionshipCatalogFile;

typedef struct SeasonCatalogFile {
    uint32_t magic,version,count,reserved;
    CampaignSeasonDefinition entries[CAMPAIGN_SEASON_MAX];
    uint32_t checksum;
} SeasonCatalogFile;

typedef struct LegacyRaceSession {
    uint32_t magic;
    uint32_t version;
    uint32_t session_id;
    int32_t event_id;
    int32_t car_id;
    uint32_t start_revision;
    uint32_t checksum;
} LegacyRaceSession;

static uint32_t Hash(const void* p,uint32_t n){
    const unsigned char* s=(const unsigned char*)p;
    uint32_t h=2166136261u,i;
    for(i=0;i<n;++i){h^=s[i];h*=16777619u;}
    return h;
}
static int Append(WCHAR* d,uint32_t cap,const WCHAR* s){
    uint32_t n=0,i=0;
    while(d[n]){++n;if(n>=cap)return 0;}
    while(s[i]){if(n+1>=cap)return 0;d[n++]=s[i++];}
    d[n]=0;return 1;
}
static int BuildPath(WCHAR* out,uint32_t cap,const WCHAR* suffix){
    DWORD n;int i;uint32_t k;
    for(k=0;k<cap;++k)out[k]=0;
    n=GetModuleFileNameW(0,out,cap);
    if(n==0||n>=cap)return 0;
    i=(int)n-1;while(i>=0&&out[i]!=L'\\'&&out[i]!=L'/')--i;
    if(i<0)return 0;out[i+1]=0;
    return Append(out,cap,suffix);
}
static int WriteBlob(const WCHAR* suffix,const void* data,DWORD size){
    WCHAR path[1024];HANDLE h;DWORD written=0;
    if(!BuildPath(path,1024,suffix))return 0;
    h=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,0,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,0);
    if(h==INVALID_HANDLE_VALUE)return 0;
    if(!WriteFile(h,data,size,&written,0)||written!=size){
        CloseHandle(h);DeleteFileW(path);return 0;
    }
    FlushFileBuffers(h);CloseHandle(h);return 1;
}
static void DeleteRel(const WCHAR* suffix){
    WCHAR path[1024];if(BuildPath(path,1024,suffix))DeleteFileW(path);
}
static void Cleanup(void){
    static const WCHAR* files[]={
        L"CampaignEvents.dat",
        L"CampaignSpecialEvents.dat",
        L"CampaignChampionships.dat",
        L"CampaignSeasons.dat",
        L"UserData\\CampaignEdition\\CampaignSave.dat",
        L"UserData\\CampaignEdition\\CampaignSave.tmp",
        L"UserData\\CampaignEdition\\CampaignSave.bak",
        L"UserData\\CampaignEdition\\CampaignRaceSession.dat",
        L"UserData\\CampaignEdition\\CampaignRaceSession.tmp",
        L"UserData\\CampaignEdition\\CampaignRaceSession.consuming",
        L"UserData\\CampaignEdition\\ActivityContext.dat",
        L"UserData\\CampaignEdition\\ActivityContext.tmp",
        L"UserData\\CampaignEdition\\SpecialEventPeriodState.dat",
        L"UserData\\CampaignEdition\\SpecialEventPeriodState.tmp",
        L"UserData\\CampaignEdition\\ChampionshipState.dat",
        L"UserData\\CampaignEdition\\ChampionshipState.tmp"
    };
    uint32_t i;
    for(i=0;i<(uint32_t)(sizeof(files)/sizeof(files[0]));++i)DeleteRel(files[i]);
}
static int WriteEvents(void){
    EventCatalogFile f;uint32_t i;unsigned char* q=(unsigned char*)&f;
    for(i=0;i<(uint32_t)sizeof(f);++i)q[i]=0;
    f.magic=CAMPAIGN_EVENT_CATALOG_MAGIC;f.version=CAMPAIGN_EVENT_CATALOG_VERSION;f.count=2;
    f.events[0].event_id=1001;f.events[0].max_stars=3;
    f.events[1].event_id=1002;f.events[1].max_stars=3;
    f.checksum=Hash(&f,(uint32_t)sizeof(f)-(uint32_t)sizeof(uint32_t));
    return WriteBlob(L"CampaignEvents.dat",&f,(DWORD)sizeof(f));
}
static int WriteSpecial(void){
    SpecialCatalogFile f;uint32_t i;unsigned char* q=(unsigned char*)&f;
    CampaignSpecialEventDefinition* d;
    for(i=0;i<(uint32_t)sizeof(f);++i)q[i]=0;
    f.magic=CAMPAIGN_SPECIAL_EVENT_MAGIC;f.version=CAMPAIGN_SPECIAL_EVENT_VERSION;f.count=1;
    d=&f.entries[0];d->special_event_id=5001;d->schedule=CAMPAIGN_SPECIAL_EVENT_PERMANENT;
    d->stage_count=2;d->stage_event_ids[0]=1001;d->stage_event_ids[1]=1002;
    f.checksum=Hash(&f,(uint32_t)sizeof(f)-(uint32_t)sizeof(uint32_t));
    return WriteBlob(L"CampaignSpecialEvents.dat",&f,(DWORD)sizeof(f));
}
static int WriteChampionship(void){
    ChampionshipCatalogFile f;uint32_t i;unsigned char* q=(unsigned char*)&f;
    CampaignChampionshipDefinition* d;
    for(i=0;i<(uint32_t)sizeof(f);++i)q[i]=0;
    f.magic=CAMPAIGN_CHAMPIONSHIP_MAGIC;f.version=CAMPAIGN_CHAMPIONSHIP_VERSION;f.count=1;
    d=&f.entries[0];d->championship_id=7001;d->round_count=2;
    d->round_event_ids[0]=1001;d->round_event_ids[1]=1002;
    d->points_by_position[0]=10;d->points_by_position[1]=8;d->points_by_position[2]=6;
    d->points_by_position[3]=5;d->points_by_position[4]=4;d->points_by_position[5]=3;
    d->points_by_position[6]=2;
    f.checksum=Hash(&f,(uint32_t)sizeof(f)-(uint32_t)sizeof(uint32_t));
    return WriteBlob(L"CampaignChampionships.dat",&f,(DWORD)sizeof(f));
}
static int WriteSeason(void){
    SeasonCatalogFile f;uint32_t i;unsigned char* q=(unsigned char*)&f;
    CampaignSeasonDefinition* d;
    for(i=0;i<(uint32_t)sizeof(f);++i)q[i]=0;
    f.magic=CAMPAIGN_SEASON_MAGIC;f.version=CAMPAIGN_SEASON_VERSION;f.count=1;
    d=&f.entries[0];d->season_id=3001;d->event_count=2;
    d->event_ids[0]=1001;d->event_ids[1]=1002;
    f.checksum=Hash(&f,(uint32_t)sizeof(f)-(uint32_t)sizeof(uint32_t));
    return WriteBlob(L"CampaignSeasons.dat",&f,(DWORD)sizeof(f));
}

static int WriteLegacyRaceSession(uint32_t session_id,int32_t event_id,uint32_t revision){
    LegacyRaceSession s;
    ZeroMemory(&s,sizeof(s));
    s.magic=0x53525852u;
    s.version=1u;
    s.session_id=session_id;
    s.event_id=event_id;
    s.car_id=0;
    s.start_revision=revision;
    s.checksum=Hash(&s,(uint32_t)sizeof(s)-(uint32_t)sizeof(uint32_t));
    return WriteBlob(L"UserData\\CampaignEdition\\CampaignRaceSession.dat",&s,(DWORD)sizeof(s));
}

static int Exec(uint32_t op,int32_t a,int32_t b,int32_t c0,int32_t d,CampaignCommand* out){
    CampaignCommand cmd;
    ZeroMemory(&cmd,sizeof(cmd));cmd.size=sizeof(cmd);cmd.op=op;
    cmd.a=a;cmd.b=b;cmd.c=c0;cmd.d=d;
    if(!CampaignExecuteCommand(&cmd))return 0;
    if(out)*out=cmd;
    return cmd.status?1:0;
}
static int Finish(uint32_t session,int placement){
    return Exec(CAMPAIGN_OP_FINISH_EVENT_RACE,(int32_t)session,placement,3,1000,0);
}
static int NoActivity(void){
    CampaignActivityContext ctx;
    ZeroMemory(&ctx,sizeof(ctx));ctx.size=sizeof(ctx);
    return CampaignActivityContextGet(&ctx)?0:1;
}

int main(void){
    CampaignCommand cmd;
    uint32_t session;

    Cleanup();
    if(!WriteEvents())return 1;
    if(!WriteSpecial())return 2;
    if(!WriteChampionship())return 3;
    if(!WriteSeason())return 44;

    /* Initialize portable Campaign directories, then emulate a pending v1 race session. */
    if(!Exec(CAMPAIGN_OP_GET_CREDITS,0,0,0,0,&cmd))return 55;
    if(!WriteLegacyRaceSession(4242u,1001,cmd.revision))return 56;

    /* Stage 2 is sequentially locked before stage 1. */
    if(Exec(CAMPAIGN_OP_BEGIN_SPECIAL_EVENT_STAGE,5001,1,0,0,&cmd))return 4;

    /* Legacy v1 Career session is migrated in-memory and remains a Career race. */
    if(!Exec(CAMPAIGN_OP_BEGIN_EVENT_RACE,1001,0,0,0,&cmd))return 5;
    session=(uint32_t)cmd.out0;
    if(session!=4242u)return 57;
    if(!Finish(session,1))return 6;
    if(!NoActivity())return 7;
    if(!Exec(CAMPAIGN_OP_SPECIAL_EVENT_STAGE,5001,0,0,0,&cmd))return 8;
    if(cmd.out1!=0)return 9;
    if(!Exec(CAMPAIGN_OP_CHAMPIONSHIP_STATUS,7001,0,0,0,&cmd))return 10;
    if(cmd.out0!=0||cmd.out1!=0)return 11;
    if(!Exec(CAMPAIGN_OP_SEASON_STATUS,3001,0,0,0,&cmd))return 45;
    if(cmd.out0!=1||cmd.out1!=2||!(cmd.out2&2))return 46;

    /* Explicit Special Event stage progresses only Special Event state. */
    if(!Exec(CAMPAIGN_OP_BEGIN_SPECIAL_EVENT_STAGE,5001,0,0,0,&cmd))return 12;
    session=(uint32_t)cmd.out0;
    if(cmd.out1!=1001)return 13;
    if(!Finish(session,1))return 14;
    if(!NoActivity())return 15;
    if(!Exec(CAMPAIGN_OP_SPECIAL_EVENT_STAGE,5001,0,0,0,&cmd))return 16;
    if(cmd.out1!=1)return 17;
    if(!Exec(CAMPAIGN_OP_SPECIAL_EVENT_STAGE,5001,1,0,0,&cmd))return 18;
    if(cmd.out2!=1)return 19;
    if(!Exec(CAMPAIGN_OP_CHAMPIONSHIP_STATUS,7001,0,0,0,&cmd))return 20;
    if(cmd.out0!=0)return 21;

    /* Explicit Championship round progresses only Championship standings. */
    if(!Exec(CAMPAIGN_OP_BEGIN_CHAMPIONSHIP_ROUND,7001,0,0,0,&cmd))return 22;
    session=(uint32_t)cmd.out0;
    if(cmd.out1!=1001)return 23;
    if(!Finish(session,2))return 24;
    if(!NoActivity())return 25;
    if(!Exec(CAMPAIGN_OP_CHAMPIONSHIP_STATUS,7001,0,0,0,&cmd))return 26;
    if(cmd.out0!=8||cmd.out1!=1)return 27;

    /* Career replay with a better P1 cannot improve the Championship. */
    if(!Exec(CAMPAIGN_OP_BEGIN_EVENT_RACE,1001,0,0,0,&cmd))return 28;
    if(!Finish((uint32_t)cmd.out0,1))return 29;
    if(!Exec(CAMPAIGN_OP_CHAMPIONSHIP_STATUS,7001,0,0,0,&cmd))return 30;
    if(cmd.out0!=8)return 31;

    /* Championship replay explicitly improves from P2(8) to P1(10). */
    if(!Exec(CAMPAIGN_OP_BEGIN_CHAMPIONSHIP_ROUND,7001,0,0,0,&cmd))return 32;
    if(!Finish((uint32_t)cmd.out0,1))return 33;
    if(!Exec(CAMPAIGN_OP_CHAMPIONSHIP_STATUS,7001,0,0,0,&cmd))return 34;
    if(cmd.out0!=10)return 35;

    /* Special stage 2 uses event 1002 but must not complete Championship round 2. */
    if(!Exec(CAMPAIGN_OP_BEGIN_SPECIAL_EVENT_STAGE,5001,1,0,0,&cmd))return 36;
    if(!Finish((uint32_t)cmd.out0,1))return 37;
    if(!Exec(CAMPAIGN_OP_CHAMPIONSHIP_ROUND,7001,1,0,0,&cmd))return 38;
    if(cmd.out2&0x10000)return 39;
    if(!Exec(CAMPAIGN_OP_SEASON_STATUS,3001,0,0,0,&cmd))return 47;
    if(cmd.out0!=1)return 48;

    /* Explicit round 2 completes the Championship, still without Career progress. */
    if(!Exec(CAMPAIGN_OP_BEGIN_CHAMPIONSHIP_ROUND,7001,1,0,0,&cmd))return 40;
    if(!Finish((uint32_t)cmd.out0,3))return 41;
    if(!Exec(CAMPAIGN_OP_CHAMPIONSHIP_STATUS,7001,0,0,0,&cmd))return 42;
    if(cmd.out0!=16||cmd.out1!=2||!(cmd.out2&0x10000))return 43;
    if(!Exec(CAMPAIGN_OP_SEASON_STATUS,3001,0,0,0,&cmd))return 49;
    if(cmd.out0!=1)return 50;

    /* Only an actual Career run of event 1002 completes the Season. */
    if(!Exec(CAMPAIGN_OP_BEGIN_EVENT_RACE,1002,0,0,0,&cmd))return 51;
    if(!Finish((uint32_t)cmd.out0,1))return 52;
    if(!Exec(CAMPAIGN_OP_SEASON_STATUS,3001,0,0,0,&cmd))return 53;
    if(cmd.out0!=2||cmd.out1!=2||!(cmd.out2&1))return 54;

    Cleanup();
    return 0;
}
