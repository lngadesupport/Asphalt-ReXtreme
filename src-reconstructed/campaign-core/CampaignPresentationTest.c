#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "CampaignPresentation.h"
#include "CampaignPresentationBindings.h"
#include "CampaignPhotoBindings.h"
#include "CampaignOriginalUiBindings.h"
#include "CampaignRaceHudBindings.h"
#include "CampaignRaceHudLayout.h"

static volatile int32_t g_test_bound_fov;
static volatile float g_test_photo_x;
static volatile float g_test_photo_y;
static volatile float g_test_photo_z;
static volatile int32_t g_test_photo_pitch;
static volatile int32_t g_test_photo_yaw;
static volatile int32_t g_test_photo_roll;
static volatile unsigned char g_test_photo_hud;
static volatile uint32_t g_test_ui_targets[16];
static volatile float g_test_hud_x;
static volatile float g_test_hud_y;
static volatile float g_test_hud_scale;
static volatile float g_test_hud_opacity;
static volatile unsigned char g_test_hud_visible;

typedef struct TestCatalogHeader {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t entry_size;
} TestCatalogHeader;

typedef struct TestBindingHeader {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t entry_size;
    uint32_t entries_hash;
    uint32_t pe_time_date_stamp;
    uint32_t pe_size_of_image;
} TestBindingHeader;

static int CurrentTestPeFingerprint(uint32_t* stamp, uint32_t* size_of_image) {
    unsigned char* module;
    uint32_t pe_off;
    unsigned char* pe;

    if (!stamp || !size_of_image) return 0;
    module = (unsigned char*)GetModuleHandleW(0);
    if (!module || module[0] != 'M' || module[1] != 'Z') return 0;
    pe_off = *(uint32_t*)(module + 0x3C);
    pe = module + pe_off;
    if (pe[0] != 'P' || pe[1] != 'E' || pe[2] != 0 || pe[3] != 0) return 0;
    if (*(uint16_t*)(pe + 24) != 0x010B) return 0;

    *stamp = *(uint32_t*)(pe + 8);
    *size_of_image = *(uint32_t*)(pe + 24 + 56);
    return 1;
}

static uint32_t TestFnv1a(const unsigned char* data, uint32_t count) {
    uint32_t h = 2166136261u;
    uint32_t i;
    for (i = 0; i < count; ++i) {
        h ^= data[i];
        h *= 16777619u;
    }
    return h;
}

typedef struct TestPhotoBindingHeader {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t entry_size;
    uint32_t entries_hash;
    uint32_t pe_time_date_stamp;
    uint32_t pe_size_of_image;
} TestPhotoBindingHeader;

static int Fail(int code) {
    return code;
}

static int TestCopyAscii(char* dst, uint32_t cap, const char* src) {
    uint32_t i = 0;
    if (!dst || !src || cap == 0) return 0;
    while (src[i]) {
        if (i + 1 >= cap) return 0;
        dst[i] = src[i];
        ++i;
    }
    dst[i] = 0;
    return 1;
}

static int WriteTestOriginalUiCatalog(void) {
    const WCHAR* path = L"prebuilt\\campaign-core\\CampaignOriginalUiBindings.dat";
    TestBindingHeader header;
    CampaignOriginalUiBinding bindings[13];
    static const char* ids[13] = {
        "settings.screen",
        "settings.row",
        "ui.slider",
        "ui.toggle",
        "ui.button",
        "ui.label",
        "ui.screen",
        "ui.panel",
        "ui.list",
        "ui.tab",
        "pause.screen",
        "pause.menu.slot",
        "race.hud"
    };
    static const uint32_t kinds[13] = {
        CAMPAIGN_ORIGINAL_UI_SCREEN,
        CAMPAIGN_ORIGINAL_UI_PANEL,
        CAMPAIGN_ORIGINAL_UI_SLIDER,
        CAMPAIGN_ORIGINAL_UI_TOGGLE,
        CAMPAIGN_ORIGINAL_UI_BUTTON,
        CAMPAIGN_ORIGINAL_UI_LABEL,
        CAMPAIGN_ORIGINAL_UI_SCREEN,
        CAMPAIGN_ORIGINAL_UI_PANEL,
        CAMPAIGN_ORIGINAL_UI_LIST,
        CAMPAIGN_ORIGINAL_UI_TAB,
        CAMPAIGN_ORIGINAL_UI_SCREEN,
        CAMPAIGN_ORIGINAL_UI_PANEL,
        CAMPAIGN_ORIGINAL_UI_PANEL
    };
    HMODULE module;
    uintptr_t base;
    uintptr_t target;
    HANDLE h;
    DWORD written = 0;
    uint32_t stamp = 0;
    uint32_t image_size = 0;
    uint32_t i;

    ZeroMemory(&header, sizeof(header));
    ZeroMemory(bindings, sizeof(bindings));

    module = GetModuleHandleW(0);
    if (!module || !CurrentTestPeFingerprint(&stamp, &image_size)) return 0;
    base = (uintptr_t)module;

    for (i = 0; i < 13; ++i) {
        target = (uintptr_t)&g_test_ui_targets[i];
        if (target <= base || target - base > 0xFFFFFFFFu) return 0;
        if (!TestCopyAscii(bindings[i].id, CAMPAIGN_ORIGINAL_UI_ID_MAX, ids[i])) return 0;
        bindings[i].kind = kinds[i];
        bindings[i].base_kind = CAMPAIGN_ORIGINAL_UI_MODULE_RVA;
        bindings[i].field_offset = 0;
        bindings[i].target_rva = (uint32_t)(target - base);
        bindings[i].semantic = i + 1u;
    }

    header.magic = 0x55495852u;
    header.version = 1;
    header.count = 13;
    header.entry_size = sizeof(CampaignOriginalUiBinding);
    header.entries_hash = TestFnv1a((const unsigned char*)bindings, sizeof(bindings));
    header.pe_time_date_stamp = stamp;
    header.pe_size_of_image = image_size;

    h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;

    if (!WriteFile(h, &header, sizeof(header), &written, 0) || written != sizeof(header)) {
        CloseHandle(h);
        return 0;
    }

    written = 0;
    if (!WriteFile(h, bindings, sizeof(bindings), &written, 0) || written != sizeof(bindings)) {
        CloseHandle(h);
        return 0;
    }

    CloseHandle(h);
    return 1;
}


static int WriteTestRaceHudCatalog(void) {
    const WCHAR* path = L"prebuilt\\campaign-core\\CampaignRaceHudBindings.dat";
    TestBindingHeader header;
    CampaignRaceHudBinding bindings[6];
    HMODULE module;
    uintptr_t base;
    uintptr_t targets[5];
    uint32_t properties[5] = {
        CAMPAIGN_RACE_HUD_PROP_X,
        CAMPAIGN_RACE_HUD_PROP_Y,
        CAMPAIGN_RACE_HUD_PROP_SCALE,
        CAMPAIGN_RACE_HUD_PROP_OPACITY,
        CAMPAIGN_RACE_HUD_PROP_VISIBLE
    };
    HANDLE h;
    DWORD written = 0;
    uint32_t stamp = 0;
    uint32_t image_size = 0;
    uint32_t i;

    ZeroMemory(&header, sizeof(header));
    ZeroMemory(bindings, sizeof(bindings));
    module = GetModuleHandleW(0);
    if (!module || !CurrentTestPeFingerprint(&stamp, &image_size)) return 0;
    base = (uintptr_t)module;

    targets[0] = (uintptr_t)&g_test_hud_x;
    targets[1] = (uintptr_t)&g_test_hud_y;
    targets[2] = (uintptr_t)&g_test_hud_scale;
    targets[3] = (uintptr_t)&g_test_hud_opacity;
    targets[4] = (uintptr_t)&g_test_hud_visible;

    for (i = 0; i < 5; ++i) {
        if (targets[i] <= base || targets[i] - base > 0xFFFFFFFFu) return 0;
        bindings[i].element = CAMPAIGN_RACE_HUD_SPEED;
        bindings[i].property = properties[i];
        bindings[i].base_kind = CAMPAIGN_PRESENTATION_BASE_MODULE_RVA;
        bindings[i].target_rva = (uint32_t)(targets[i] - base);
        bindings[i].field_offset = 0;
        bindings[i].flags = 1;
        if (properties[i] == CAMPAIGN_RACE_HUD_PROP_VISIBLE) {
            bindings[i].value_kind = CAMPAIGN_PRESENTATION_VALUE_U8_BOOL;
            bindings[i].scale_divisor = 1;
        } else {
            bindings[i].value_kind = CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED;
            bindings[i].scale_divisor = 1000;
        }
    }

    bindings[5].element = CAMPAIGN_RACE_HUD_NITRO;
    bindings[5].property = CAMPAIGN_RACE_HUD_PROP_X;
    bindings[5].base_kind = CAMPAIGN_RACE_HUD_BASE_GUI_ARGUMENT;
    bindings[5].target_rva = 0;
    bindings[5].field_offset = 4;
    bindings[5].value_kind = CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED;
    bindings[5].scale_divisor = 1000;
    bindings[5].flags = 1;

    header.magic = 0x42485852u;
    header.version = 1;
    header.count = 6;
    header.entry_size = sizeof(CampaignRaceHudBinding);
    header.entries_hash = TestFnv1a((const unsigned char*)bindings, sizeof(bindings));
    header.pe_time_date_stamp = stamp;
    header.pe_size_of_image = image_size;

    h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;
    if (!WriteFile(h, &header, sizeof(header), &written, 0) || written != sizeof(header)) {
        CloseHandle(h);
        return 0;
    }
    written = 0;
    if (!WriteFile(h, bindings, sizeof(bindings), &written, 0) || written != sizeof(bindings)) {
        CloseHandle(h);
        return 0;
    }
    CloseHandle(h);
    return 1;
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

static int WriteTestPhotoBindingCatalog(void) {
    const WCHAR* path = L"prebuilt\\campaign-core\\CampaignPhotoBindings.dat";
    TestPhotoBindingHeader header;
    CampaignPhotoBinding bindings[7];
    HANDLE h;
    DWORD written = 0;
    HMODULE module;
    uintptr_t base;
    uintptr_t targets[7];
    uint32_t semantics[7] = {
        CAMPAIGN_PHOTO_BIND_POSITION_X,
        CAMPAIGN_PHOTO_BIND_POSITION_Y,
        CAMPAIGN_PHOTO_BIND_POSITION_Z,
        CAMPAIGN_PHOTO_BIND_PITCH,
        CAMPAIGN_PHOTO_BIND_YAW,
        CAMPAIGN_PHOTO_BIND_ROLL,
        CAMPAIGN_PHOTO_BIND_HUD_VISIBLE
    };
    uint32_t i;

    ZeroMemory(&header, sizeof(header));
    ZeroMemory(bindings, sizeof(bindings));
    module = GetModuleHandleW(0);
    if (!module) return 0;
    base = (uintptr_t)module;

    targets[0] = (uintptr_t)&g_test_photo_x;
    targets[1] = (uintptr_t)&g_test_photo_y;
    targets[2] = (uintptr_t)&g_test_photo_z;
    targets[3] = (uintptr_t)&g_test_photo_pitch;
    targets[4] = (uintptr_t)&g_test_photo_yaw;
    targets[5] = (uintptr_t)&g_test_photo_roll;
    targets[6] = (uintptr_t)&g_test_photo_hud;

    for (i = 0; i < 7; ++i) {
        if (targets[i] <= base || targets[i] - base > 0xFFFFFFFFu) return 0;
        bindings[i].semantic = semantics[i];
        bindings[i].base_kind = CAMPAIGN_PRESENTATION_BASE_MODULE_RVA;
        bindings[i].target_rva = (uint32_t)(targets[i] - base);
        bindings[i].field_offset = 0;
        bindings[i].scale_divisor = 1;
        bindings[i].flags = 1;
        if (i < 3) {
            bindings[i].value_kind = CAMPAIGN_PRESENTATION_VALUE_FLOAT_SCALED;
            bindings[i].scale_divisor = 1000;
        } else if (i == 6) {
            bindings[i].value_kind = CAMPAIGN_PRESENTATION_VALUE_U8_BOOL;
        } else {
            bindings[i].value_kind = CAMPAIGN_PRESENTATION_VALUE_I32;
        }
    }

    header.magic = 0x48505852u;
    header.version = 2;
    header.count = 7;
    header.entry_size = sizeof(CampaignPhotoBinding);
    if (!CurrentTestPeFingerprint(
            &header.pe_time_date_stamp,
            &header.pe_size_of_image)) return 0;
    header.entries_hash = TestFnv1a(
        (const unsigned char*)bindings,
        (uint32_t)sizeof(bindings)
    );

    h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;

    if (!WriteFile(h, &header, sizeof(header), &written, 0) || written != sizeof(header)) {
        CloseHandle(h);
        return 0;
    }
    written = 0;
    if (!WriteFile(h, bindings, sizeof(bindings), &written, 0) || written != sizeof(bindings)) {
        CloseHandle(h);
        return 0;
    }
    CloseHandle(h);
    return 1;
}

static int WriteTestBindingCatalog(void) {
    const WCHAR* path = L"prebuilt\\campaign-core\\CampaignPresentationBindings.dat";
    TestBindingHeader header;
    CampaignPresentationBinding binding;
    HANDLE h;
    DWORD written = 0;
    HMODULE module;
    uintptr_t base;
    uintptr_t target;
    const char id[] = "fov";
    uint32_t i;

    ZeroMemory(&header, sizeof(header));
    ZeroMemory(&binding, sizeof(binding));

    module = GetModuleHandleW(0);
    if (!module) return 0;
    base = (uintptr_t)module;
    target = (uintptr_t)&g_test_bound_fov;
    if (target <= base || target - base > 0xFFFFFFFFu) return 0;

    for (i = 0; i < sizeof(id); ++i) binding.id[i] = id[i];
    binding.base_kind = CAMPAIGN_PRESENTATION_BASE_MODULE_RVA;
    binding.target_rva = (uint32_t)(target - base);
    binding.field_offset = 0;
    binding.value_kind = CAMPAIGN_PRESENTATION_VALUE_I32;
    binding.scale_divisor = 1;
    binding.flags = CAMPAIGN_PRESENTATION_BINDING_VERIFIED;

    header.magic = 0x42505852u;
    header.version = 2;
    header.count = 1;
    header.entry_size = sizeof(CampaignPresentationBinding);
    if (!CurrentTestPeFingerprint(
            &header.pe_time_date_stamp,
            &header.pe_size_of_image)) return 0;
    header.entries_hash = TestFnv1a(
        (const unsigned char*)&binding,
        (uint32_t)sizeof(binding)
    );

    h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;

    if (!WriteFile(h, &header, sizeof(header), &written, 0) || written != sizeof(header)) {
        CloseHandle(h);
        return 0;
    }

    written = 0;
    if (!WriteFile(h, &binding, sizeof(binding), &written, 0) || written != sizeof(binding)) {
        CloseHandle(h);
        return 0;
    }

    CloseHandle(h);
    return 1;
}

static int CorruptReplayTail(const WCHAR* path) {
    HANDLE h;
    LARGE_INTEGER pos;
    BYTE value;
    DWORD got = 0;
    DWORD written = 0;

    h = CreateFileW(path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;

    pos.QuadPart = -1;
    if (!SetFilePointerEx(h, pos, 0, FILE_END)) {
        CloseHandle(h);
        return 0;
    }

    if (!ReadFile(h, &value, 1, &got, 0) || got != 1) {
        CloseHandle(h);
        return 0;
    }

    value ^= 0x5Au;
    pos.QuadPart = -1;
    if (!SetFilePointerEx(h, pos, 0, FILE_END)) {
        CloseHandle(h);
        return 0;
    }

    if (!WriteFile(h, &value, 1, &written, 0) || written != 1) {
        CloseHandle(h);
        return 0;
    }

    FlushFileBuffers(h);
    CloseHandle(h);
    return 1;
}

int main(void) {
    CampaignPresentationSettings settings;
    CampaignPresentationSettings loaded;
    CampaignReplayMetadata metadata;
    CampaignReplayMetadata metadata_readback;
    CampaignReplaySample sample;
    CampaignReplaySample readback;
    CampaignReplayMarker marker;
    CampaignReplayMarker marker_readback;
    CampaignReplayInfo info;
    CampaignReplayPlaybackState playback;
    CampaignReplayLibraryEntry library_entry;
    CampaignPhotoState photo;
    CampaignPhotoState photo_readback;
    CampaignPresentationDiagnostics diagnostics;
    const WCHAR* replay_path = L"prebuilt\\campaign-core\\presentation-test.rexreplay";
    WCHAR auto_path[1024];

    ZeroMemory(&settings, sizeof(settings));
    ZeroMemory(&loaded, sizeof(loaded));
    ZeroMemory(&metadata, sizeof(metadata));
    ZeroMemory(&metadata_readback, sizeof(metadata_readback));
    ZeroMemory(&sample, sizeof(sample));
    ZeroMemory(&readback, sizeof(readback));
    ZeroMemory(&marker, sizeof(marker));
    ZeroMemory(&marker_readback, sizeof(marker_readback));
    ZeroMemory(&info, sizeof(info));
    ZeroMemory(&playback, sizeof(playback));
    ZeroMemory(&library_entry, sizeof(library_entry));
    ZeroMemory(&photo, sizeof(photo));
    ZeroMemory(&photo_readback, sizeof(photo_readback));
    ZeroMemory(&diagnostics, sizeof(diagnostics));
    ZeroMemory(auto_path, sizeof(auto_path));

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

    metadata.size = sizeof(metadata);
    metadata.version = CAMPAIGN_REPLAY_FORMAT_VERSION;
    metadata.event_id = 101;
    metadata.track_id = 12;
    metadata.player_car_id = 7;
    metadata.race_mode = 1;
    metadata.session_id = 0x12345678u;
    if (!CampaignReplaySetMetadata(&metadata)) return Fail(21);

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

    DeleteFileW(auto_path);
    DeleteFileW(replay_path);
    if (!CampaignReplaySave(replay_path)) return Fail(28);

    if (!CampaignReplayGetAutoPath(auto_path, 1024)) return Fail(28);
    DeleteFileW(auto_path);
    if (!CampaignReplaySaveAuto()) return Fail(28);
    if (GetFileAttributesW(auto_path) == INVALID_FILE_ATTRIBUTES) return Fail(28);

    if (!CampaignReplayLibraryRefresh()) return Fail(28);
    if (CampaignReplayLibraryCount() != 1) return Fail(28);

    library_entry.size = sizeof(library_entry);
    if (!CampaignReplayLibraryGet(0, &library_entry)) return Fail(28);
    if (library_entry.metadata.event_id != 101 ||
        library_entry.metadata.session_id != 0x12345678u ||
        library_entry.sample_count != 2 ||
        library_entry.marker_count != 1 ||
        library_entry.duration_ms != 100) return Fail(28);

    if (!CampaignReplayLibraryLoad(0)) return Fail(28);
    if (!CampaignReplayLibraryDelete(0)) return Fail(28);
    if (CampaignReplayLibraryCount() != 0) return Fail(28);

    if (!CampaignReplayClear()) return Fail(29);
    if (!CampaignReplayLoad(replay_path)) return Fail(30);

    metadata_readback.size = sizeof(metadata_readback);
    if (!CampaignReplayGetMetadata(&metadata_readback)) return Fail(31);
    if (metadata_readback.event_id != 101 ||
        metadata_readback.track_id != 12 ||
        metadata_readback.player_car_id != 7 ||
        metadata_readback.session_id != 0x12345678u) return Fail(32);

    ZeroMemory(&info, sizeof(info));
    info.size = sizeof(info);
    if (!CampaignReplayGetInfo(&info)) return Fail(31);
    if (info.sample_count != 2 || info.marker_count != 1) return Fail(32);

    if (!CampaignReplayGetSample(1, &readback)) return Fail(33);
    if (readback.time_ms != 200 || readback.entity_id != 2) return Fail(34);

    if (!CampaignReplayGetMarker(0, &marker_readback)) return Fail(35);
    if (marker_readback.type != CAMPAIGN_REPLAY_MARKER_JUMP ||
        marker_readback.time_ms != 150) return Fail(36);

    playback.size = sizeof(playback);
    if (!CampaignReplayGetPlaybackState(&playback)) return Fail(37);
    if (!playback.loaded || playback.first_time_ms != 100 || playback.last_time_ms != 200) return Fail(38);

    if (!CampaignReplaySetSpeed(250)) return Fail(39);
    if (CampaignReplaySetSpeed(333)) return Fail(70);
    if (!CampaignReplaySeek(150)) return Fail(71);
    if (CampaignReplaySeek(250)) return Fail(72);
    if (!CampaignReplayPlay()) return Fail(73);

    ZeroMemory(&playback, sizeof(playback));
    playback.size = sizeof(playback);
    if (!CampaignReplayGetPlaybackState(&playback)) return Fail(44);
    if (!playback.playing || playback.current_time_ms != 150 || playback.speed_permille != 250) return Fail(45);

    if (!CampaignReplayAdvance(100)) return Fail(46);
    ZeroMemory(&playback, sizeof(playback));
    playback.size = sizeof(playback);
    if (!CampaignReplayGetPlaybackState(&playback)) return Fail(47);
    if (!playback.playing || playback.current_time_ms != 175) return Fail(48);

    if (!CampaignReplayStep(1, 0)) return Fail(49);
    ZeroMemory(&playback, sizeof(playback));
    playback.size = sizeof(playback);
    if (!CampaignReplayGetPlaybackState(&playback)) return Fail(50);
    if (playback.playing || playback.current_time_ms != 200) return Fail(51);

    if (!CampaignReplayStep(-1, 0)) return Fail(52);
    ZeroMemory(&playback, sizeof(playback));
    playback.size = sizeof(playback);
    if (!CampaignReplayGetPlaybackState(&playback)) return Fail(53);
    if (playback.current_time_ms != 100) return Fail(54);
    if (!CampaignReplaySeek(150)) return Fail(55);
    if (!CampaignReplayPause()) return Fail(56);

    ZeroMemory(&readback, sizeof(readback));
    if (!CampaignReplayGetSampleAtTime(170, 0, &readback)) return Fail(47);
    if (readback.time_ms != 200) return Fail(48);

    ZeroMemory(&marker_readback, sizeof(marker_readback));
    if (!CampaignReplayNextMarker(100, &marker_readback)) return Fail(49);
    if (marker_readback.time_ms != 150) return Fail(80);
    if (!CampaignReplayPreviousMarker(200, &marker_readback)) return Fail(81);
    if (marker_readback.time_ms != 150) return Fail(82);

    if (!CorruptReplayTail(replay_path)) return Fail(83);
    if (CampaignReplayLoad(replay_path)) return Fail(84);

    ZeroMemory(&photo, sizeof(photo));
    photo.size = sizeof(photo);
    photo.camera_mode = CAMPAIGN_PHOTO_CAMERA_FREE;
    photo.hide_hud = 1;
    photo.position_x = 12.5f;
    photo.position_y = 3.0f;
    photo.position_z = -8.0f;
    photo.pitch_x100 = -500;
    photo.yaw_x100 = 9000;
    photo.roll_x100 = 250;
    photo.move_speed_x1000 = 1500;
    photo.fov_x100 = 0;

    if (CampaignPhotoBindingsCount() != 0) return Fail(40);
    if (CampaignPhotoBindingsReady(CAMPAIGN_PHOTO_CAMERA_FREE)) return Fail(41);
    if (CampaignPhotoEnter(&photo)) return Fail(42);

    if (!WriteTestPhotoBindingCatalog()) return Fail(43);
    if (!CampaignPhotoBindingsLoad()) return Fail(44);
    if (CampaignPhotoBindingsCount() != 7) return Fail(45);
    if (!CampaignPhotoBindingsReady(CAMPAIGN_PHOTO_CAMERA_FREE)) return Fail(46);

    g_test_photo_x = 1.25f;
    g_test_photo_y = 2.5f;
    g_test_photo_z = -3.75f;
    g_test_photo_pitch = 100;
    g_test_photo_yaw = 200;
    g_test_photo_roll = 300;
    g_test_photo_hud = 1;

    if (!CampaignPhotoEnter(&photo)) return Fail(47);

    ZeroMemory(&photo_readback, sizeof(photo_readback));
    photo_readback.size = sizeof(photo_readback);
    if (!CampaignPhotoGet(&photo_readback)) return Fail(48);
    if (!photo_readback.active ||
        photo_readback.camera_mode != CAMPAIGN_PHOTO_CAMERA_FREE ||
        photo_readback.position_x != 12.5f ||
        photo_readback.position_y != 3.0f ||
        photo_readback.position_z != -8.0f ||
        photo_readback.pitch_x100 != -500 ||
        photo_readback.yaw_x100 != 9000 ||
        photo_readback.roll_x100 != 250 ||
        photo_readback.move_speed_x1000 != 1500) return Fail(49);

    g_test_photo_hud = 1;
    if (!CampaignPhotoBindingsApply(&photo_readback)) return Fail(50);
    if (g_test_photo_x != 12.5f ||
        g_test_photo_y != 3.0f ||
        g_test_photo_z != -8.0f ||
        g_test_photo_pitch != -500 ||
        g_test_photo_yaw != 9000 ||
        g_test_photo_roll != 250 ||
        g_test_photo_hud != 0) return Fail(51);

    if (!CampaignPhotoMove(500, -500, 1000)) return Fail(107);
    if (g_test_photo_x != 13.0f ||
        g_test_photo_y != 2.5f ||
        g_test_photo_z != -7.0f) return Fail(108);

    if (!CampaignPhotoRotate(100, -200, 50)) return Fail(109);
    if (g_test_photo_pitch != -400 ||
        g_test_photo_yaw != 8800 ||
        g_test_photo_roll != 300) return Fail(110);

    if (!CampaignPhotoSetMoveSpeed(2500)) return Fail(111);
    ZeroMemory(&photo_readback, sizeof(photo_readback));
    photo_readback.size = sizeof(photo_readback);
    if (!CampaignPhotoGet(&photo_readback) ||
        photo_readback.move_speed_x1000 != 2500) return Fail(112);

    /* No verified FOV binding exists in this test catalog. */
    if (CampaignPhotoSetFov(6500)) return Fail(113);

    if (!CampaignPhotoResetView()) return Fail(114);
    if (g_test_photo_x != 1.25f ||
        g_test_photo_y != 2.5f ||
        g_test_photo_z != -3.75f ||
        g_test_photo_pitch != 100 ||
        g_test_photo_yaw != 200 ||
        g_test_photo_roll != 300 ||
        g_test_photo_hud != 0) return Fail(115);

    if (!CampaignPhotoExit()) return Fail(52);
    if (g_test_photo_x != 1.25f ||
        g_test_photo_y != 2.5f ||
        g_test_photo_z != -3.75f ||
        g_test_photo_pitch != 100 ||
        g_test_photo_yaw != 200 ||
        g_test_photo_roll != 300 ||
        g_test_photo_hud != 1) return Fail(56);

    ZeroMemory(&diagnostics, sizeof(diagnostics));
    diagnostics.size = sizeof(diagnostics);
    if (!CampaignPresentationGetDiagnostics(&diagnostics)) return Fail(53);
    if (diagnostics.photo_active != 0 ||
        diagnostics.photo_binding_count != 7 ||
        !diagnostics.photo_free_camera_ready ||
        diagnostics.original_ui_binding_count != 0 ||
        diagnostics.original_ui_feature_mask != 0 ||
        diagnostics.race_hud_binding_count != 0 ||
        diagnostics.race_hud_original_ui_ready != 0) return Fail(54);

    if (CampaignOriginalUiBindingsCount() != 0) return Fail(116);
    if (CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_GRAPHICS_SETTINGS)) return Fail(117);
    if (!WriteTestOriginalUiCatalog()) return Fail(118);
    if (!CampaignOriginalUiBindingsLoad()) return Fail(119);
    if (CampaignOriginalUiBindingsCount() != 13) return Fail(120);
    if (!CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_GRAPHICS_SETTINGS) ||
        !CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_CAMERA_SETTINGS) ||
        !CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_REPLAY) ||
        !CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_PHOTO_MODE) ||
        !CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_RACE_HUD) ||
        !CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_CHALLENGES) ||
        !CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_ACHIEVEMENTS)) return Fail(121);
    if (CampaignOriginalUiFeatureReady(CAMPAIGN_ORIGINAL_UI_FEATURE_RESULTS)) return Fail(144);
    if (CampaignOriginalUiBindingsResolve("ui.button") != (void*)&g_test_ui_targets[4]) return Fail(122);

    if (CampaignRaceHudBindingsCount() != 0) return Fail(123);
    {
        CampaignRaceHudElementState hud;
        ZeroMemory(&hud, sizeof(hud));
        hud.size = sizeof(hud);
        hud.element = CAMPAIGN_RACE_HUD_SPEED;
        hud.set_flags =
            CAMPAIGN_RACE_HUD_SET_X |
            CAMPAIGN_RACE_HUD_SET_Y |
            CAMPAIGN_RACE_HUD_SET_SCALE |
            CAMPAIGN_RACE_HUD_SET_OPACITY |
            CAMPAIGN_RACE_HUD_SET_VISIBLE;
        hud.x_x1000 = 12500;
        hud.y_x1000 = 42000;
        hud.scale_x1000 = 1250;
        hud.opacity_x1000 = 750;
        hud.visible = 1;

        if (CampaignRaceHudApplyElement(&hud)) return Fail(124);
        if (!WriteTestRaceHudCatalog()) return Fail(125);
        if (!CampaignRaceHudBindingsLoad()) return Fail(126);
        if (CampaignRaceHudBindingsCount() != 6) return Fail(127);
        if (!CampaignRaceHudElementReady(CAMPAIGN_RACE_HUD_SPEED, hud.set_flags)) return Fail(128);
        if (!CampaignRaceHudApplyElement(&hud)) return Fail(129);
        if (g_test_hud_x != 12.5f ||
            g_test_hud_y != 42.0f ||
            g_test_hud_scale != 1.25f ||
            g_test_hud_opacity != 0.75f ||
            g_test_hud_visible != 1) return Fail(130);

        {
            struct TestGuiHud {
                uint32_t pad;
                float nitro_x;
            } gui;
            CampaignRaceHudElementState nitro;
            ZeroMemory(&gui, sizeof(gui));
            ZeroMemory(&nitro, sizeof(nitro));
            nitro.size = sizeof(nitro);
            nitro.element = CAMPAIGN_RACE_HUD_NITRO;
            nitro.set_flags = CAMPAIGN_RACE_HUD_SET_X;
            nitro.x_x1000 = 33000;

            if (CampaignRaceHudApplyElement(&nitro)) return Fail(141);
            if (!CampaignRaceHudApplyElementFromGui(&gui, &nitro)) return Fail(142);
            if (gui.nitro_x != 33.0f) return Fail(143);
        }

        if (!CampaignRaceHudLayoutReset()) return Fail(131);
        if (!CampaignRaceHudLayoutSet(&hud)) return Fail(132);
        if (CampaignRaceHudLayoutCount() != 1) return Fail(133);
        if (!CampaignRaceHudLayoutSave()) return Fail(134);

        g_test_hud_x = 0.0f;
        g_test_hud_y = 0.0f;
        g_test_hud_scale = 0.0f;
        g_test_hud_opacity = 0.0f;
        g_test_hud_visible = 0;

        if (!CampaignRaceHudLayoutLoad()) return Fail(135);
        if (CampaignRaceHudLayoutCount() != 1) return Fail(136);
        ZeroMemory(&hud, sizeof(hud));
        hud.size = sizeof(hud);
        if (!CampaignRaceHudLayoutGet(0, &hud)) return Fail(137);
        if (hud.element != CAMPAIGN_RACE_HUD_SPEED ||
            hud.x_x1000 != 12500 ||
            hud.y_x1000 != 42000 ||
            hud.scale_x1000 != 1250 ||
            hud.opacity_x1000 != 750 ||
            hud.visible != 1) return Fail(138);
        if (!CampaignRaceHudLayoutApply()) return Fail(139);
        if (g_test_hud_x != 12.5f ||
            g_test_hud_y != 42.0f ||
            g_test_hud_scale != 1.25f ||
            g_test_hud_opacity != 0.75f ||
            g_test_hud_visible != 1) return Fail(140);
    }

    if (CampaignPresentationCatalogCount() != 0) return Fail(50);
    if (!WriteTestCapabilityCatalog()) return Fail(51);
    if (!CampaignPresentationCatalogLoad()) return Fail(52);
    if (CampaignPresentationCatalogCount() != 1) return Fail(83);
    if (!WriteTestBindingCatalog()) return Fail(84);
    if (!CampaignPresentationBindingsLoad()) return Fail(85);
    if (CampaignPresentationBindingsCount() != 1) return Fail(86);

    g_test_bound_fov = 7000;
    {
        int32_t value = 0;
        int32_t bound = 0;
        if (!CampaignPresentationCatalogGetValue(0, &value)) return Fail(87);
        if (value != 7000) return Fail(88);
        if (!CampaignPresentationCatalogSetValue(0, 7500)) return Fail(89);
        if (g_test_bound_fov != 7500) return Fail(90);
        if (!CampaignPresentationBindingsRead("fov", &bound) || bound != 7500) return Fail(91);
        if (CampaignPresentationCatalogSetValue(0, 7555)) return Fail(92);
        if (!CampaignPresentationCatalogGetValue(0, &value) || value != 7500) return Fail(93);
        if (!CampaignPresentationCatalogResetValue(0)) return Fail(94);
        if (g_test_bound_fov != 7000) return Fail(95);
        if (!CampaignPresentationCatalogGetValue(0, &value) || value != 7000) return Fail(96);
    }

    ZeroMemory(&loaded, sizeof(loaded));
    loaded.size = sizeof(loaded);
    if (!CampaignPresentationGetSettings(&loaded)) return Fail(91);
    settings = loaded;
    settings.fov_x100 = 7500;
    if (!CampaignPresentationSetSettings(&settings)) return Fail(97);
    if (g_test_bound_fov != 7500) return Fail(98);

    ZeroMemory(&diagnostics, sizeof(diagnostics));
    diagnostics.size = sizeof(diagnostics);
    if (!CampaignPresentationGetDiagnostics(&diagnostics)) return Fail(99);
    if (diagnostics.verified_capability_count != 1 ||
        diagnostics.verified_binding_count != 1 ||
        diagnostics.original_ui_binding_count != 13 ||
        diagnostics.original_ui_feature_mask != 0x7Fu ||
        diagnostics.race_hud_binding_count != 6 ||
        diagnostics.race_hud_original_ui_ready != 1 ||
        diagnostics.race_hud_layout_count != 1) return Fail(100);

    if (!CampaignReplayStart(256)) return Fail(101);
    ZeroMemory(&sample, sizeof(sample));
    sample.entity_id = 1;
    sample.rotation_w = 1.0f;
    sample.time_ms = 1000;
    if (!CampaignReplayRecordFrame(&sample)) return Fail(102);
    sample.time_ms = 1010;
    if (!CampaignReplayRecordFrame(&sample)) return Fail(103);
    sample.time_ms = 1033;
    if (!CampaignReplayRecordFrame(&sample)) return Fail(104);

    ZeroMemory(&info, sizeof(info));
    info.size = sizeof(info);
    if (!CampaignReplayGetInfo(&info)) return Fail(105);
    if (info.sample_count != 2 ||
        info.throttled_samples != 1 ||
        info.dropped_samples != 0) return Fail(106);
    CampaignReplayStop();

    DeleteFileW(replay_path);
    DeleteFileW(L"prebuilt\\campaign-core\\ReXtremePresentation.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\ReXtremePresentation.tmp");
    DeleteFileW(L"prebuilt\\campaign-core\\ReXtremePresentation.bak");
    DeleteFileW(auto_path);
    DeleteFileW(L"prebuilt\\campaign-core\\CampaignPresentationOptions.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\CampaignPresentationBindings.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\CampaignPhotoBindings.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\CampaignOriginalUiBindings.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\CampaignRaceHudBindings.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\UserData\\RaceHudLayout.dat");
    DeleteFileW(L"prebuilt\\campaign-core\\UserData\\RaceHudLayout.tmp");
    DeleteFileW(L"prebuilt\\campaign-core\\ReXtreme.ini");

    return 0;
}
