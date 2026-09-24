#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignEventCatalog.h"
#include "CampaignChampionshipCatalog.h"

typedef struct TestEventCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignEventDefinition events[CAMPAIGN_EVENT_CATALOG_MAX_EVENTS];
    uint32_t checksum;
} TestEventCatalogFile;

typedef struct TestChampionshipCatalogFile {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    CampaignChampionshipDefinition entries[CAMPAIGN_CHAMPIONSHIP_MAX];
    uint32_t checksum;
} TestChampionshipCatalogFile;

static uint32_t Hash(const void* p, uint32_t n) {
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
    if(!WriteFile(h,data,size,&written,0)||written!=size){CloseHandle(h);DeleteFileW(path);return 0;}
    FlushFileBuffers(h);CloseHandle(h);return 1;
}
static int WriteEvents(void){
    TestEventCatalogFile file;unsigned char* q=(unsigned char*)&file;uint32_t i;
    for(i=0;i<(uint32_t)sizeof(file);++i)q[i]=0;
    file.magic=CAMPAIGN_EVENT_CATALOG_MAGIC;
    file.version=CAMPAIGN_EVENT_CATALOG_VERSION;
    file.count=3;
    file.events[0].event_id=1001;file.events[0].completion_node_id=1001;file.events[0].max_stars=3;
    file.events[1].event_id=1002;file.events[1].completion_node_id=1002;file.events[1].max_stars=3;
    file.events[2].event_id=1003;file.events[2].completion_node_id=1003;file.events[2].max_stars=3;
    file.checksum=Hash(&file,(uint32_t)sizeof(file)-(uint32_t)sizeof(uint32_t));
    return WriteBlob(L"CampaignEvents.dat",&file,(DWORD)sizeof(file));
}
static int WriteChampionships(void){
    TestChampionshipCatalogFile file;unsigned char* q=(unsigned char*)&file;uint32_t i;
    CampaignChampionshipDefinition* d;
    for(i=0;i<(uint32_t)sizeof(file);++i)q[i]=0;
    file.magic=CAMPAIGN_CHAMPIONSHIP_MAGIC;
    file.version=CAMPAIGN_CHAMPIONSHIP_VERSION;
    file.count=1;
    d=&file.entries[0];
    d->championship_id=7001;
    d->round_count=3;
    d->round_event_ids[0]=1001;
    d->round_event_ids[1]=1002;
    d->round_event_ids[2]=1003;
    d->points_by_position[0]=10;
    d->points_by_position[1]=8;
    d->points_by_position[2]=6;
    d->points_by_position[3]=5;
    d->points_by_position[4]=4;
    d->points_by_position[5]=3;
    d->points_by_position[6]=2;
    file.checksum=Hash(&file,(uint32_t)sizeof(file)-(uint32_t)sizeof(uint32_t));
    return WriteBlob(L"CampaignChampionships.dat",&file,(DWORD)sizeof(file));
}
static void Cleanup(void){
    WCHAR path[1024];
    if(BuildPath(path,1024,L"CampaignEvents.dat"))DeleteFileW(path);
    if(BuildPath(path,1024,L"CampaignChampionships.dat"))DeleteFileW(path);
    if(BuildPath(path,1024,L"UserData\\CampaignEdition\\ChampionshipState.dat"))DeleteFileW(path);
    if(BuildPath(path,1024,L"UserData\\CampaignEdition\\ChampionshipState.tmp"))DeleteFileW(path);
}

int main(void){
    CampaignRaceMetrics m;
    CampaignChampionshipStatus status;
    CampaignChampionshipRoundStatus round;

    Cleanup();
    if(!WriteEvents())return 1;
    if(!WriteChampionships())return 2;
    if(CampaignEventCatalogCount()!=3)return 3;
    if(CampaignChampionshipCatalogCount()!=1)return 4;
    if(!CampaignChampionshipsResetState())return 5;

    ZeroMemory(&status,sizeof(status));status.size=sizeof(status);
    if(!CampaignChampionshipsGetStatus(7001,&status))return 6;
    if(status.total_points!=0||status.completed_rounds!=0||status.completed)return 7;

    ZeroMemory(&m,sizeof(m));m.size=sizeof(m);m.version=CAMPAIGN_RACE_METRICS_VERSION;
    m.placement=2;
    if(!CampaignChampionshipsRecordRound(7001,1001,&m))return 8;
    ZeroMemory(&status,sizeof(status));status.size=sizeof(status);
    if(!CampaignChampionshipsGetStatus(7001,&status))return 9;
    if(status.total_points!=8||status.completed_rounds!=1||status.completed)return 10;

    /* Worse replay does not reduce standings. Better replay improves only the delta. */
    m.placement=3;
    if(!CampaignChampionshipsRecordRound(7001,1001,&m))return 11;
    m.placement=1;
    if(!CampaignChampionshipsRecordRound(7001,1001,&m))return 12;
    ZeroMemory(&round,sizeof(round));round.size=sizeof(round);
    if(!CampaignChampionshipsGetRoundStatus(7001,0,&round))return 13;
    if(round.best_placement!=1||round.points!=10||!round.completed)return 14;

    m.placement=3;
    if(!CampaignChampionshipsRecordRound(7001,1002,&m))return 15;
    m.placement=1;
    if(!CampaignChampionshipsRecordRound(7001,1003,&m))return 16;

    ZeroMemory(&status,sizeof(status));status.size=sizeof(status);
    if(!CampaignChampionshipsGetStatus(7001,&status))return 17;
    if(status.total_points!=26||status.completed_rounds!=3||!status.completed)return 18;

    if(!CampaignChampionshipsReload())return 19;
    ZeroMemory(&status,sizeof(status));status.size=sizeof(status);
    if(!CampaignChampionshipsGetStatus(7001,&status))return 20;
    if(status.total_points!=26||status.completed_rounds!=3||!status.completed)return 21;

    Cleanup();
    return 0;
}
