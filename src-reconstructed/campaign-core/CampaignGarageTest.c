#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignCore.h"
#include "CampaignCatalog.h"
#include "CampaignUpgradeCatalog.h"

typedef struct TestVehicleCatalogFile {
    uint32_t magic,version,count,reserved;
    CampaignVehicleRecipe vehicles[CAMPAIGN_CATALOG_MAX_VEHICLES];
    uint32_t checksum;
} TestVehicleCatalogFile;

typedef struct TestUpgradeCatalogFile {
    uint32_t magic,version,count,reserved;
    CampaignUpgradeDefinition entries[CAMPAIGN_UPGRADE_CATALOG_MAX_ENTRIES];
    uint32_t checksum;
} TestUpgradeCatalogFile;

static TestVehicleCatalogFile g_vehicle_catalog;
static TestUpgradeCatalogFile g_upgrade_catalog;

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
        L"CampaignCatalog.dat",
        L"CampaignUpgrades.dat",
        L"UserData\\CampaignEdition\\CampaignSave.dat",
        L"UserData\\CampaignEdition\\CampaignSave.tmp",
        L"UserData\\CampaignEdition\\CampaignSave.bak",
        L"UserData\\CampaignEdition\\CampaignRaceSession.dat",
        L"UserData\\CampaignEdition\\CampaignRaceSession.tmp",
        L"UserData\\CampaignEdition\\CampaignRaceSession.consuming",
        L"UserData\\CampaignEdition\\ActivityContext.dat",
        L"UserData\\CampaignEdition\\ActivityContext.tmp"
    };
    uint32_t i;
    for(i=0;i<(uint32_t)(sizeof(files)/sizeof(files[0]));++i)DeleteRel(files[i]);
}
static int WriteCatalogs(void){
    CampaignVehicleRecipe* v;
    CampaignUpgradeDefinition* u;
    ZeroMemory(&g_vehicle_catalog,sizeof(g_vehicle_catalog));
    ZeroMemory(&g_upgrade_catalog,sizeof(g_upgrade_catalog));

    g_vehicle_catalog.magic=CAMPAIGN_CATALOG_MAGIC;
    g_vehicle_catalog.version=CAMPAIGN_CATALOG_VERSION;
    g_vehicle_catalog.count=2;

    v=&g_vehicle_catalog.vehicles[0];
    v->car_id=2001;
    v->acquisition_type=CAMPAIGN_ACQUIRE_CREDITS;
    v->cost=1000;
    v->class_id=2;

    v=&g_vehicle_catalog.vehicles[1];
    v->car_id=2002;
    v->acquisition_type=CAMPAIGN_ACQUIRE_BLUEPRINT;
    v->item_id=9001;
    v->cost=5;
    v->class_id=3;

    g_vehicle_catalog.checksum=Hash(
        &g_vehicle_catalog,
        (uint32_t)sizeof(g_vehicle_catalog)-(uint32_t)sizeof(uint32_t)
    );

    g_upgrade_catalog.magic=CAMPAIGN_UPGRADE_CATALOG_MAGIC;
    g_upgrade_catalog.version=CAMPAIGN_UPGRADE_CATALOG_VERSION;
    g_upgrade_catalog.count=3;

    u=&g_upgrade_catalog.entries[0];
    u->car_id=2001;u->kind=CAMPAIGN_UPGRADE_KIND_STANDARD;u->part_slot=0;u->target_level=1;
    u->cost_type=CAMPAIGN_COST_CREDITS;u->cost=500;

    u=&g_upgrade_catalog.entries[1];
    u->car_id=2001;u->kind=CAMPAIGN_UPGRADE_KIND_STANDARD;u->part_slot=0;u->target_level=2;
    u->cost_type=CAMPAIGN_COST_CREDITS;u->cost=1000;

    u=&g_upgrade_catalog.entries[2];
    u->car_id=2001;u->kind=CAMPAIGN_UPGRADE_KIND_PROKIT;u->part_slot=0;u->target_level=1;
    u->cost_type=CAMPAIGN_COST_FREE;u->cost=0;

    g_upgrade_catalog.checksum=Hash(
        &g_upgrade_catalog,
        (uint32_t)sizeof(g_upgrade_catalog)-(uint32_t)sizeof(uint32_t)
    );

    return WriteBlob(L"CampaignCatalog.dat",&g_vehicle_catalog,(DWORD)sizeof(g_vehicle_catalog)) &&
           WriteBlob(L"CampaignUpgrades.dat",&g_upgrade_catalog,(DWORD)sizeof(g_upgrade_catalog));
}
static int Exec(uint32_t op,int32_t a,int32_t b,int32_t c0,int32_t d,CampaignCommand* out){
    CampaignCommand cmd;
    ZeroMemory(&cmd,sizeof(cmd));
    cmd.size=sizeof(cmd);cmd.op=op;cmd.a=a;cmd.b=b;cmd.c=c0;cmd.d=d;
    if(!CampaignExecuteCommand(&cmd)||!cmd.status)return 0;
    if(out)*out=cmd;
    return 1;
}

int main(void){
    CampaignCommand cmd;
    int32_t flags;

    Cleanup();
    if(!WriteCatalogs())return 1;

    if(!Exec(CAMPAIGN_OP_GARAGE_COUNT,0,0,0,0,&cmd)||cmd.out0!=2)return 2;
    if(!Exec(CAMPAIGN_OP_GARAGE_CAR_ID_AT,0,0,0,0,&cmd)||cmd.out0!=2001)return 3;
    if(!Exec(CAMPAIGN_OP_GARAGE_CAR_ID_AT,1,0,0,0,&cmd)||cmd.out0!=2002)return 4;

    if(!Exec(CAMPAIGN_OP_GARAGE_CAR_STATUS,2001,0,0,0,&cmd))return 5;
    flags=cmd.out0;
    if(flags&CAMPAIGN_GARAGE_OWNED)return 6;
    if(!(flags&CAMPAIGN_GARAGE_UNLOCKED)||!(flags&CAMPAIGN_GARAGE_ACQUIRABLE))return 7;
    if(cmd.out1!=2||cmd.out2!=CAMPAIGN_ACQUIRE_CREDITS)return 8;

    if(!Exec(CAMPAIGN_OP_GARAGE_ACQUISITION,2001,0,0,0,&cmd))return 9;
    if(cmd.out0!=0||cmd.out1!=1000||cmd.out2!=0)return 10;

    if(Exec(CAMPAIGN_OP_GARAGE_SELECT_CAR,2001,0,0,0,&cmd))return 11;
    if(!Exec(CAMPAIGN_OP_ACQUIRE_CATALOG,2001,0,0,0,&cmd))return 12;
    if(!Exec(CAMPAIGN_OP_GARAGE_CAR_STATUS,2001,0,0,0,&cmd))return 13;
    flags=cmd.out0;
    if(!(flags&CAMPAIGN_GARAGE_OWNED)||(flags&CAMPAIGN_GARAGE_ACQUIRABLE))return 14;

    if(!Exec(CAMPAIGN_OP_GARAGE_SELECT_CAR,2001,0,0,0,&cmd)||cmd.out0!=2001)return 15;
    if(!Exec(CAMPAIGN_OP_RELOAD,0,0,0,0,&cmd))return 16;
    if(!Exec(CAMPAIGN_OP_GARAGE_CAR_STATUS,2001,0,0,0,&cmd))return 17;
    if(!(cmd.out0&CAMPAIGN_GARAGE_SELECTED))return 18;

    if(!Exec(CAMPAIGN_OP_GARAGE_PART_STATUS,2001,CAMPAIGN_UPGRADE_KIND_STANDARD,0,0,&cmd))return 19;
    if(cmd.out0!=0||cmd.out1!=1||cmd.out2!=3)return 20;
    if(!Exec(CAMPAIGN_OP_GARAGE_NEXT_PART_COST,2001,CAMPAIGN_UPGRADE_KIND_STANDARD,0,0,&cmd))return 21;
    if(cmd.out0!=CAMPAIGN_COST_CREDITS||cmd.out1!=0||cmd.out2!=500)return 22;

    if(!Exec(CAMPAIGN_OP_APPLY_UPGRADE,2001,0,1,0,&cmd))return 23;
    if(!Exec(CAMPAIGN_OP_GARAGE_PART_STATUS,2001,CAMPAIGN_UPGRADE_KIND_STANDARD,0,0,&cmd))return 24;
    if(cmd.out0!=1||cmd.out1!=2||cmd.out2!=3)return 25;
    if(!Exec(CAMPAIGN_OP_GARAGE_NEXT_PART_COST,2001,CAMPAIGN_UPGRADE_KIND_STANDARD,0,0,&cmd))return 26;
    if(cmd.out2!=1000)return 27;

    if(!Exec(CAMPAIGN_OP_GARAGE_PART_STATUS,2001,CAMPAIGN_UPGRADE_KIND_PROKIT,0,0,&cmd))return 28;
    if(cmd.out0!=0||cmd.out1!=1||cmd.out2!=3)return 29;
    if(!Exec(CAMPAIGN_OP_APPLY_PROKIT,2001,0,1,0,&cmd))return 30;
    if(!Exec(CAMPAIGN_OP_GARAGE_PART_STATUS,2001,CAMPAIGN_UPGRADE_KIND_PROKIT,0,0,&cmd))return 31;
    if(cmd.out0!=1||cmd.out1!=0||cmd.out2!=0)return 32;

    if(!Exec(CAMPAIGN_OP_GARAGE_CAR_STATUS,2002,0,0,0,&cmd))return 33;
    if(cmd.out0&CAMPAIGN_GARAGE_ACQUIRABLE)return 34;
    if(!Exec(CAMPAIGN_OP_INVENTORY_ADD,9001,5,0,0,&cmd))return 35;
    if(!Exec(CAMPAIGN_OP_GARAGE_CAR_STATUS,2002,0,0,0,&cmd))return 36;
    if(!(cmd.out0&CAMPAIGN_GARAGE_ACQUIRABLE))return 37;
    if(!Exec(CAMPAIGN_OP_ACQUIRE_CATALOG,2002,0,0,0,&cmd))return 38;
    if(!Exec(CAMPAIGN_OP_GARAGE_CAR_STATUS,2002,0,0,0,&cmd))return 39;
    if(!(cmd.out0&CAMPAIGN_GARAGE_OWNED)||(cmd.out0&CAMPAIGN_GARAGE_ACQUIRABLE))return 40;

    Cleanup();
    return 0;
}
