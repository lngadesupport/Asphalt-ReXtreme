#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignPresentation.h"

typedef struct TestCatalogHeader {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t entry_size;
} TestCatalogHeader;

static int Fail(int code) {
    return code;
}

static int WriteTestCapabilityCatalog(void) {
    const WCHAR* path = L"prebuilt\\campaign-core\\CampaignPresentationOptions.dat";
    TestCatalogHeader header;
    CampaignPresentationCapability capability;
    HANDLE h;
    DWORD written = 0;
    const char id[] = "fov";
    uint32_t i;

    ZeroMemory(&header, sizeof(header));
    ZeroMemory(&capability, sizeof(capability));

    header.magic = 0x43505852u;
    header.version = 1;
    header.count = 1;
    header.entry_size = sizeof(CampaignPresentationCapability);

    for (i = 0; i < sizeof(id); ++i) capability.id[i] = id[i];
    capability.kind = CAMPAIGN_PRESENTATION_CAPABILITY_SLIDER;
    capability.minimum = 5000;
    capability.maximum = 10000;
    capability.step = 100;
    capability.original_value = 7000;
    capability.flags = CAMPAIGN_PRESENTATION_CAPABILITY_VERIFIED;

    h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;

    if (!WriteFile(h, &header, sizeof(header), &written, 0) || written != sizeof(header)) {
        CloseHandle(h);
        return 0;
    }

    written = 0;
    if (!WriteFile(h, &capability, sizeof(capability), &written, 0) || written != sizeof(capability)) {
        CloseHandle(h);
        return 0;
    }

    CloseHandle(h);
    return 1;
}

int main(void) {
    CampaignPresentationSettings settings;
    CampaignPresentationSettings loaded;
    CampaignReplaySample sample;
    CampaignReplaySample readback;
    CampaignReplayMarker marker;
    CampaignReplayMarker marker_readback;
    CampaignReplayInfo info;
    CampaignPhotoState photo;
    CampaignPhotoState photo_readback;
    const WCHAR* replay_path = L"prebuilt\\campaign-core\\presentation-test.rexreplay";

    ZeroMemory(&settings, sizeof(settings));
    ZeroMemory(&loaded, sizeof(loaded));
    ZeroMemory(&sample, sizeof(sample));
    ZeroMemory(&readback, sizeof(readback));
    ZeroMemory(&marker, sizeof(marker));
    ZeroMemory(&marker_readback, sizeof(marker_readback));
    ZeroMemory(&info, sizeof(info));
    ZeroMemory(&photo, sizeof(photo));
    ZeroMemory(&photo_readback, sizeof(photo_readback));

    if (!CampaignPresentationResetSettings()) return Fail(10);

    loaded.size = sizeof(loaded);
    if (!CampaignPresentationGetSettings(&loaded)) return Fail(11);
    if (loaded.fov_x100 != 0) return Fail(12);

    settings = loaded;
    settings.fov_x100 = 7500;
    if (CampaignPresentationSetSettings(&settings)) return Fail(13);

    settings = loaded;
    settings.flags = CAMPAIGN_PRESENTATION_REPLAY_ENABLED;
    if (!CampaignPresentationSetSettings(&settings)) return Fail(14);
    if (!CampaignPresentationSaveSettings()) return Fail(15);
    if (!CampaignPresentationResetSettings()) return Fail(16);
    if (!CampaignPresentationLoadSettings()) return Fail(17);

    ZeroMemory(&loaded, sizeof(loaded));
    loaded.size = sizeof(loaded);
    if (!CampaignPresentationGetSettings(&loaded)) return Fail(18);
    if (loaded.fov_x100 != 0) return Fail(19);
    if (loaded.flags != CAMPAIGN_PRESENTATION_REPLAY_ENABLED) return Fail(20);

    if (!CampaignReplayStart(8)) return Fail(20);

    sample.time_ms = 100;
    sample.entity_id = 1;
    sample.position_x = 1.0f;
    sample.rotation_w = 1.0f;
    if (!CampaignReplayRecord(&sample)) return Fail(21);

    sample.time_ms = 200;
    sample.entity_id = 2;
    sample.position_x = 2.0f;
    if (!CampaignReplayRecord(&sample)) return Fail(22);

    marker.time_ms = 150;
    marker.type = CAMPAIGN_REPLAY_MARKER_JUMP;
    marker.entity_id = 1;
    marker.value = 7;
    if (!CampaignReplayAddMarker(&marker)) return Fail(23);

    if (!CampaignReplayStop()) return Fail(24);

    info.size = sizeof(info);
    if (!CampaignReplayGetInfo(&info)) return Fail(25);
    if (info.sample_count != 2 || info.marker_count != 1) return Fail(26);
    if (info.first_time_ms != 100 || info.last_time_ms != 200) return Fail(27);

    DeleteFileW(replay_path);
    if (!CampaignReplaySave(replay_path)) return Fail(28);

    if (!CampaignReplayClear()) return Fail(29);
    if (!CampaignReplayLoad(replay_path)) return Fail(30);

    ZeroMemory(&info, sizeof(info));
    info.size = sizeof(info);
    if (!CampaignReplayGetInfo(&info)) return Fail(31);
    if (info.sample_count != 2 || info.marker_count != 1) return Fail(32);

    if (!CampaignReplayGetSample(1, &readback)) return Fail(33);
    if (readback.time_ms != 200 || readback.entity_id != 2) return Fail(34);

    if (!CampaignReplayGetMarker(0, &marker_readback)) return Fail(35);
    if (marker_readback.type != CAMPAIGN_REPLAY_MARKER_JUMP ||
        marker_readback.time_ms != 150) return Fail(36);

    photo.size = sizeof(photo);
    photo.camera_mode = CAMPAIGN_PHOTO_CAMERA_FREE;
    photo.hide_hud = 1;
    photo.fov_x100 = 6500;
    if (!CampaignPhotoEnter(&photo)) return Fail(40);

    photo_readback.size = sizeof(photo_readback);
    if (!CampaignPhotoGet(&photo_readback)) return Fail(41);
    if (!photo_readback.active || photo_readback.fov_x100 != 6500) return Fail(42);
    if (!CampaignPhotoExit()) return Fail(43);

    if (CampaignPresentationCatalogCount() != 0) return Fail(50);
    if (!WriteTestCapabilityCatalog()) return Fail(51);
    if (!CampaignPresentationCatalogLoad()) return Fail(52);
    if (CampaignPresentationCatalogCount() != 1) return Fail(53);

    {
        int32_t value = 0;
        if (!CampaignPresentationCatalogGetValue(0, &value)) return Fail(54);
        if (value != 7000) return Fail(55);
        if (!CampaignPresentationCatalogSetValue(0, 7500)) return Fail(56);
        if (CampaignPresentationCatalogSetValue(0, 7555)) return Fail(57);
        if (!CampaignPresentationCatalogGetValue(0, &value) || value != 7500) return Fail(58);
        if (!CampaignPresentationCatalogResetValue(0)) return Fail(59);
        if (!CampaignPresentationCatalogGetValue(0, &value) || value != 7000) return Fail(60);
    }

    ZeroMemory(&loaded, sizeof(loaded));
    loaded.size = sizeof(loaded);
    if (!CampaignPresentationGetSettings(&loaded)) return Fail(61);
    settings = loaded;
    settings.fov_x100 = 7500;
    if (!CampaignPresentationSetSettings(&settings)) return Fail(62);

    DeleteFileW(replay_path);
    DeleteFileW(L"prebuilt\\campaign-core\\ReXtremePresentation.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\ReXtremePresentation.tmp");
    DeleteFileW(L"prebuilt\\campaign-core\\ReXtremePresentation.bak");
    DeleteFileW(L"prebuilt\\campaign-core\\CampaignPresentationOptions.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\ReXtreme.ini");

    return 0;
}
